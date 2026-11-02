"""Ukážka na /demo — živé AI generovanie pre neprihláseného návštevníka.

Demo je jediné miesto, kde AI kredity míňa ktokoľvek z internetu bez účtu,
takže výdavok drží na uzde trojica opatrení:

1. **Cache podľa témy** — rovnaká téma sa negeneruje druhýkrát (`demo_generations`).
2. **Denný strop** — po vyčerpaní sa už nevolá AI, ale podá sa najobľúbenejšia
   uložená sada. Návštevník vidí hotový výsledok, nie chybu.
3. **Zabudované sady** — keď je cache prázdna (prvý deň, chýbajúca migrácia),
   ukážka aj tak niečo ukáže.

Rate limit na IP rieši router, tu ide o spotrebu naprieč všetkými návštevníkmi.
"""
import json
import os
import random
import re
import unicodedata
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.models.demo_generation import DemoGeneration
from app.models.word import Word, clean_example
from app.services.learning import CARD, Entry, build_item, pools_from_pairs
from app.utils import utcnow

# Koľko slovíčok ukážka vygeneruje. Päť stačí na predvedenie a je to zlomok
# ceny bežného generovania (25 slov).
DEMO_WORD_COUNT = 5

# Priehradky slov, ktoré sa po kartičkách vrátia ako otázka: výber významu,
# doplnenie do vety a počúvanie alebo ďalšia veta, rovnako ako v appke.
DEMO_QUESTION_BOXES = (1, 2, 3)

# Strop skutočných AI volaní za deň naprieč všetkými návštevníkmi.
# Env premenná, nech sa dá stiahnuť bez deploya kódu.
DEMO_AI_DAILY_LIMIT = int(os.getenv("DEMO_AI_DAILY_LIMIT", "60"))

# Dĺžka témy — dlhší text nie je téma, ale pokus použiť demo ako prekladač.
TOPIC_MAX_LENGTH = 80


# Núdzové sady, keď je cache prázdna. Zámerne krátke a v jazykovej dvojici,
# ktorú appka ponúka ako predvolenú.
BUNDLED_SETS = [
    {
        "topic": "cestovanie lietadlom",
        "language_from": "en",
        "language_to": "sk",
        "category_name": "Na letisku",
        "words": [
            {"original": "boarding pass", "translation": "palubný lístok",
             "example_sentence": "Show your boarding pass at the desk.",
             "example_translation": "Pri prepážke ukáž palubný lístok."},
            {"original": "departure", "translation": "odlet",
             "example_sentence": "Our departure is at nine o'clock.",
             "example_translation": "Náš odlet je o deviatej."},
            {"original": "luggage", "translation": "batožina",
             "example_sentence": "My luggage is too heavy.",
             "example_translation": "Moja batožina je príliš ťažká."},
            {"original": "gate", "translation": "brána",
             "example_sentence": "The flight leaves from gate twelve.",
             "example_translation": "Let odlieta z brány dvanásť."},
            {"original": "delay", "translation": "meškanie",
             "example_sentence": "There is a two-hour delay.",
             "example_translation": "Let má dvojhodinové meškanie."},
        ],
    },
    {
        "topic": "v reštaurácii",
        "language_from": "en",
        "language_to": "sk",
        "category_name": "V reštaurácii",
        "words": [
            {"original": "starter", "translation": "predjedlo",
             "example_sentence": "I would like soup as a starter.",
             "example_translation": "Ako predjedlo si dám polievku."},
            {"original": "main course", "translation": "hlavné jedlo",
             "example_sentence": "The main course was delicious.",
             "example_translation": "Hlavné jedlo bolo výborné."},
            {"original": "bill", "translation": "účet",
             "example_sentence": "Could we have the bill, please?",
             "example_translation": "Môžeme dostať účet, prosím?"},
            {"original": "waiter", "translation": "čašník",
             "example_sentence": "The waiter brought us the menu.",
             "example_translation": "Čašník nám priniesol jedálny lístok."},
            {"original": "tip", "translation": "prepitné",
             "example_sentence": "We left a small tip.",
             "example_translation": "Nechali sme malé prepitné."},
        ],
    },
    {
        # Anglické rozhranie ponúka španielčinu — tie isté slová, aké mala
        # ukážka natvrdo pred prerobením na živé generovanie.
        "topic": "everyday Spanish",
        "language_from": "es",
        "language_to": "en",
        "category_name": "Everyday Spanish",
        "words": [
            {"original": "casa", "translation": "house",
             "example_sentence": "Mi casa está cerca del parque.",
             "example_translation": "My house is near the park."},
            {"original": "agua", "translation": "water",
             "example_sentence": "Quiero un vaso de agua.",
             "example_translation": "I would like a glass of water."},
            {"original": "amistad", "translation": "friendship",
             "example_sentence": "Nuestra amistad es muy importante.",
             "example_translation": "Our friendship is very important."},
            {"original": "viaje", "translation": "travel",
             "example_sentence": "El viaje fue muy largo.",
             "example_translation": "The journey was very long."},
            {"original": "sonrisa", "translation": "smile",
             "example_sentence": "Tienes una sonrisa bonita.",
             "example_translation": "You have a lovely smile."},
        ],
    },
    {
        "topic": "job interview",
        "language_from": "en",
        "language_to": "sk",
        "category_name": "Pracovný pohovor",
        "words": [
            {"original": "strengths", "translation": "silné stránky",
             "example_sentence": "What are your main strengths?",
             "example_translation": "Aké sú tvoje hlavné silné stránky?"},
            {"original": "experience", "translation": "skúsenosti",
             "example_sentence": "I have five years of experience.",
             "example_translation": "Mám päť rokov skúseností."},
            {"original": "notice period", "translation": "výpovedná lehota",
             "example_sentence": "My notice period is two months.",
             "example_translation": "Moja výpovedná lehota sú dva mesiace."},
            {"original": "salary expectations", "translation": "platové očakávania",
             "example_sentence": "What are your salary expectations?",
             "example_translation": "Aké sú tvoje platové očakávania?"},
            {"original": "team player", "translation": "tímový hráč",
             "example_sentence": "I am a good team player.",
             "example_translation": "Som dobrý tímový hráč."},
        ],
    },
]


def normalize_topic(topic: str) -> str:
    """Kľúč cache: malé písmená, bez diakritiky, jedna medzera medzi slovami.

    „Cestovanie Lietadlom" aj „cestovanie  lietadlom" tak trafia tú istú sadu —
    inak by cache minula skoro každú druhú požiadavku.
    """
    text = unicodedata.normalize("NFD", topic or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:120]


def _row_to_set(row: DemoGeneration, source: str) -> dict:
    return {
        "topic": row.topic,
        "category_name": row.category_name,
        "language_from": row.language_from,
        "language_to": row.language_to,
        "words": json.loads(row.words_json),
        "source": source,
    }


def find_cached(db: Session, topic_key: str, language_from: str, language_to: str):
    """Hotová sada pre rovnakú tému a jazykovú dvojicu (a započíta zásah)."""
    try:
        row = (
            db.query(DemoGeneration)
            .filter(
                DemoGeneration.topic_key == topic_key,
                DemoGeneration.language_from == language_from,
                DemoGeneration.language_to == language_to,
            )
            .order_by(DemoGeneration.created_at.desc())
            .first()
        )
    except (ProgrammingError, OperationalError):
        db.rollback()
        return None
    if not row:
        return None
    row.hits = (row.hits or 0) + 1
    db.commit()
    return _row_to_set(row, "cache")


def ai_calls_today(db: Session) -> int:
    """Koľko skutočných AI volaní ukážka minula dnes (= koľko riadkov pribudlo)."""
    since = utcnow() - timedelta(days=1)
    try:
        return int(
            db.query(func.count(DemoGeneration.id))
            .filter(DemoGeneration.created_at >= since)
            .scalar()
            or 0
        )
    except (ProgrammingError, OperationalError):
        db.rollback()
        # Bez tabuľky nevieme spotrebu zmerať — radšej AI nevolať vôbec, nech sa
        # chýbajúca migrácia neprejaví ako nekontrolovaný výdavok.
        return DEMO_AI_DAILY_LIMIT


def budget_left(db: Session) -> int:
    return max(0, DEMO_AI_DAILY_LIMIT - ai_calls_today(db))


def store_generated(
    db: Session, *, topic: str, topic_key: str, language_from: str,
    language_to: str, category_name, words: list,
) -> None:
    """Uloží čerstvo vygenerovanú sadu do cache (a tým ju započíta do stropu)."""
    try:
        db.add(DemoGeneration(
            topic_key=topic_key,
            topic=topic[:200],
            language_from=language_from,
            language_to=language_to,
            category_name=(category_name[:120] if category_name else None),
            words_json=json.dumps(words, ensure_ascii=False),
        ))
        db.commit()
    except (ProgrammingError, OperationalError):
        # Cache je pohodlie, nie podmienka — návštevník sadu dostane aj tak.
        db.rollback()


def fallback_set(db: Session, language_from: str, language_to: str) -> dict:
    """Náhrada, keď je strop vyčerpaný: najžiadanejšia uložená sada, inak zabudovaná."""
    try:
        row = (
            db.query(DemoGeneration)
            .filter(
                DemoGeneration.language_from == language_from,
                DemoGeneration.language_to == language_to,
            )
            .order_by(DemoGeneration.hits.desc(), DemoGeneration.created_at.desc())
            .first()
        )
    except (ProgrammingError, OperationalError):
        db.rollback()
        row = None
    if row:
        return _row_to_set(row, "sample")

    for bundled in BUNDLED_SETS:
        if bundled["language_from"] == language_from and bundled["language_to"] == language_to:
            return {**bundled, "source": "sample"}
    return {**BUNDLED_SETS[0], "source": "sample"}


def build_lesson(demo_set: dict, rng=random) -> list:
    """Úlohy ukážky, zložené tým istým kódom ako učenie v appke.

    Každé slovo sa najprv ukáže na kartičke a prvé tri sa potom vrátia ako
    otázka. V appke sa to deje po dňoch, ukážka to stiahne do jednej minúty.
    Starší záznam v cache nemá vety, takže namiesto dopĺňania dostane výber.
    """
    language_from, language_to = demo_set["language_from"], demo_set["language_to"]
    words = [
        Word(
            id=index, original_word=item["original"], translation=item["translation"],
            language_from=language_from, language_to=language_to,
            example_sentence=item.get("example_sentence"),
            example_translation=item.get("example_translation"),
        )
        for index, item in enumerate(demo_set["words"], start=1)
    ]
    rng.shuffle(words)
    pools = pools_from_pairs([(w.original_word, w.translation) for w in words])

    cards = [build_item(Entry(word, 0, None, None), None) for word in words]
    questions = [
        build_item(Entry(word, box, None, None), pools, rng)
        for word, box in zip(words, DEMO_QUESTION_BOXES)
    ]
    # Sada s jediným slovom nemá z čoho skladať možnosti a otázka by bola len
    # tá istá kartička druhýkrát.
    return cards + [item for item in questions if item["exercise"] != CARD]


def normalize_words(raw_words: list) -> list:
    """Z AI payloadu spraví slová s prípadnou vetou — bez prázdnych a duplicít.

    Duplicitné heslo je v ukážke horšie než o slovo menej: návštevník by videl
    to isté slovo dvakrát s iným prekladom hneď v prvom kontakte s produktom.
    """
    words = []
    seen = set()
    for item in raw_words or []:
        original = (item.get("original_word") or item.get("original") or "").strip()
        translation = (item.get("translation") or "").strip()
        if not original or not translation:
            continue
        key = original.casefold()
        if key in seen:
            continue
        seen.add(key)
        word = {"original": original, "translation": translation}
        sentence = clean_example(item.get("example_sentence"))
        if sentence:
            word["example_sentence"] = sentence
            word["example_translation"] = clean_example(item.get("example_translation"))
        words.append(word)
    return words
