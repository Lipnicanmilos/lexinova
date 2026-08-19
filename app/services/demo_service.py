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
import re
import unicodedata
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.models.demo_generation import DemoGeneration
from app.utils import utcnow

# Koľko slovíčok ukážka vygeneruje. Päť stačí na predvedenie a je to zlomok
# ceny bežného generovania (25 slov).
DEMO_WORD_COUNT = 5

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
            {"original": "boarding pass", "translation": "palubný lístok"},
            {"original": "departure", "translation": "odlet"},
            {"original": "luggage", "translation": "batožina"},
            {"original": "gate", "translation": "brána"},
            {"original": "delay", "translation": "meškanie"},
        ],
    },
    {
        "topic": "v reštaurácii",
        "language_from": "en",
        "language_to": "sk",
        "category_name": "V reštaurácii",
        "words": [
            {"original": "starter", "translation": "predjedlo"},
            {"original": "main course", "translation": "hlavné jedlo"},
            {"original": "bill", "translation": "účet"},
            {"original": "waiter", "translation": "čašník"},
            {"original": "tip", "translation": "prepitné"},
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
            {"original": "casa", "translation": "house"},
            {"original": "agua", "translation": "water"},
            {"original": "amistad", "translation": "friendship"},
            {"original": "viaje", "translation": "travel"},
            {"original": "sonrisa", "translation": "smile"},
        ],
    },
    {
        "topic": "job interview",
        "language_from": "en",
        "language_to": "sk",
        "category_name": "Pracovný pohovor",
        "words": [
            {"original": "strengths", "translation": "silné stránky"},
            {"original": "experience", "translation": "skúsenosti"},
            {"original": "notice period", "translation": "výpovedná lehota"},
            {"original": "salary expectations", "translation": "platové očakávania"},
            {"original": "team player", "translation": "tímový hráč"},
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


def normalize_words(raw_words: list) -> list:
    """Z AI payloadu spraví [{original, translation}] — bez prázdnych a duplicít.

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
        words.append({"original": original, "translation": translation})
    return words
