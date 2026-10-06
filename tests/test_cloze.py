"""Dopĺňanie do viet — druhý režim obrazovky testu.

Úlohu pripravuje server: v príkladovej vete nájde slovo, vynechá ho a pridá
nesprávne možnosti z tej istej sady. Slovo, ktoré sa vo vete nenašlo, do úlohy
nejde — vynechať nesprávne miesto je horšie než mať o úlohu menej.

Heslo z viacerých slov (fráza, dialóg) príkladovú vetu nepotrebuje: vynechá sa
slovo priamo z neho. Bez toho sada fráz skončila na prázdnej obrazovke
„žiadne slovíčko nemá príkladovú vetu", hoci každá fráza vetou je.
"""
import random

import pytest

from app.models.category import Category
from app.models.user import User
from app.models.word import KnowledgeLevel, Word
from app.services.cloze import (
    BLANK_OPTIONS,
    ClozePools,
    build_task,
    is_phrase,
    pick_options,
    split_phrase,
    split_sentence,
)


def _register_and_login(client, email):
    client.post("/api/v1/register", json={"email": email, "password": "Abcdef12"})
    client.post("/api/v1/login", json={"email": email, "password": "Abcdef12"})


def _seed(client, db_factory, email, words, name="Letisko"):
    """Sada so slovami priamo v databáze; `words` sú (slovo, preklad, veta, úroveň)."""
    db = db_factory()
    try:
        user_id = db.query(User).filter(User.email == email).one().id
        category = Category(name=name, description="", user_id=user_id)
        db.add(category)
        db.commit()
        db.add_all([
            Word(original_word=original, translation=translation, category_id=category.id,
                 user_id=user_id, example_sentence=sentence,
                 example_translation=f"preklad: {sentence}" if sentence else None,
                 knowledge_level=level)
            for original, translation, sentence, level in words
        ])
        db.commit()
        return category.id
    finally:
        db.close()


def _start(client, category_id, levels=("dont_know", "learning", "know")):
    return client.post("/api/v1/words/cloze/start", json={
        "category_id": category_id, "knowledge_levels": list(levels), "limit": 1000})


AIRPORT = [
    ("gate", "brána", "The gate is closed.", KnowledgeLevel.DONT_KNOW),
    ("delay", "meškanie", "There was a long delay.", KnowledgeLevel.KNOW),
    ("travel", "cestovať", "We travelled to Italy.", KnowledgeLevel.DONT_KNOW),
    ("ticket", "lístok", None, KnowledgeLevel.DONT_KNOW),         # bez vety
    ("go", "ísť", "I went home early.", KnowledgeLevel.DONT_KNOW),  # vo vete sa nenájde
]


@pytest.fixture(autouse=True)
def _clean(db_factory):
    yield
    db = db_factory()
    try:
        db.query(Word).delete()
        db.query(Category).delete()
        db.commit()
    finally:
        db.close()


# ── hľadanie slova vo vete ──────────────────────────────────────────────────

@pytest.mark.parametrize("sentence, headword, expected", [
    ("The gate is closed.", "gate", ("The ", "gate", " is closed.")),
    ("Gates are closed.", "gate", ("", "Gates", " are closed.")),              # veľké písmeno, množné číslo
    ("We travelled to Italy.", "travel", ("We ", "travelled", " to Italy.")),
    ("She studies every evening.", "study", ("She ", "studies", " every evening.")),
    ("He is making dinner.", "make", ("He is ", "making", " dinner.")),
    ("We want to travel more.", "to travel", ("We want ", "to travel", " more.")),
    ("We travel a lot.", "to travel", ("We ", "travel", " a lot.")),           # heslo s časticou
    ("Go now, please.", "go (went, gone)", ("", "Go", " now, please.")),       # zátvorka sa zahodí
    ("Mám rád čerstvý chlieb.", "čerstvý", ("Mám rád ", "čerstvý", " chlieb.")),
])
def test_split_finds_the_word(sentence, headword, expected):
    assert split_sentence(sentence, headword) == expected


@pytest.mark.parametrize("sentence, headword", [
    ("I went home early.", "go"),            # nepravidelný tvar
    ("It is a good idea.", "go"),            # krátke heslo sa nehľadá ako začiatok slova
    ("I ran in the park.", "run"),
    ("The category is empty.", "cat"),       # „cat" nie je „category"
    ("When did you go?", "When did you go?"),  # heslo je celá veta — nezostal by kontext
    ("", "gate"),
    (None, "gate"),
    ("The gate is closed.", ""),
])
def test_split_gives_up_rather_than_blank_the_wrong_place(sentence, headword):
    assert split_sentence(sentence, headword) is None


def test_options_hold_the_answer_once_and_other_words_of_the_set():
    options = pick_options("gate", ["gate", "Gate", "delay", "ticket", "flight", "seat"],
                           rng=random.Random(1))

    assert len(options) == BLANK_OPTIONS and len(set(options)) == BLANK_OPTIONS
    assert options.count("gate") == 1 and "Gate" not in options


def test_options_need_at_least_one_other_word():
    assert pick_options("gate", ["gate", "GATE "]) == []
    assert sorted(pick_options("gate", ["gate", "delay"])) == ["delay", "gate"]


# ── frázy ───────────────────────────────────────────────────────────────────

PHRASES = [
    "When did you go? – Last September.",
    "Have you made the coffee yet? – Yes, I've just made it.",
    "How long have you lived here?",
]


@pytest.mark.parametrize("headword, expected", [
    ("gate", False), ("to travel", False), ("der Hund", False),
    ("look forward to", True), ("How long have you lived here?", True),
    ("I've just made it", True),          # apostrof slovo nedelí
])
def test_three_words_make_a_phrase(headword, expected):
    assert is_phrase(headword) is expected


def test_phrase_gap_is_a_longer_word_that_does_not_start_a_sentence():
    """„When" aj „Last" začínajú vetu — veľké písmeno by ich medzi možnosťami
    prezradilo. „did", „you", „go" sú prikrátke."""
    for seed in range(30):
        before, hidden, after = split_phrase("When did you go? – Last September.", random.Random(seed))
        assert hidden == "September"
        assert before + hidden + after == "When did you go? – Last September."


def test_phrase_options_match_the_capitalisation_of_the_answer_when_they_can():
    pools = ClozePools.from_headwords([
        "We met in September last year.", "She moved to London in March.",
        "They visited Paris and Vienna.", "He works every Monday morning.",
    ])

    for seed in range(20):
        task = build_task("We met in September last year.", "preklad", None, None,
                          pools, random.Random(seed))
        capital = task.answer[:1].isupper()
        assert all(option[:1].isupper() == capital for option in task.options), task.options


def test_phrase_gap_falls_back_to_short_words_and_gives_up_on_non_phrases():
    assert split_phrase("How are you?", random.Random(0))[1] in {"How", "are", "you"}
    assert split_phrase("to travel") is None
    assert split_phrase("") is None and split_phrase(None) is None


def test_phrase_needs_no_example_sentence():
    pools = ClozePools.from_headwords(PHRASES)

    task = build_task(PHRASES[2], "Ako dlho tu bývaš?", None, None, pools, random.Random(2))

    assert task.before + task.hidden + task.after == PHRASES[2]
    assert task.answer == task.hidden and task.answer in task.options
    assert task.translation == "Ako dlho tu bývaš?"
    # Nesprávne možnosti sú slová z iných fráz, nie z tejto.
    own = {"how", "long", "have", "you", "lived", "here"}
    assert not {o.casefold() for o in task.options if o != task.answer} & own


def test_phrase_used_whole_in_its_example_sentence_is_treated_like_a_word():
    pools = ClozePools.from_headwords(["look forward to", "give up", "gate"])

    task = build_task("look forward to", "tešiť sa na", "I look forward to the trip.",
                      "Teším sa na výlet.", pools, random.Random(0))

    assert (task.before, task.hidden, task.after) == ("I ", "look forward to", " the trip.")
    assert task.answer == "look forward to" and task.translation == "Teším sa na výlet."


def test_a_word_gets_other_words_as_options_before_whole_phrases():
    """V zmiešanej sade by sa celá fráza medzi slovami dala vylúčiť na prvý pohľad."""
    pools = ClozePools.from_headwords(["gate", "delay", "ticket", "seat"] + PHRASES)

    task = build_task("gate", "brána", "The gate is closed.", None, pools, random.Random(0))
    assert not set(task.options) & set(PHRASES)

    lonely = ClozePools.from_headwords(["gate"] + PHRASES)
    task = build_task("gate", "brána", "The gate is closed.", None, lonely, random.Random(0))
    assert task and set(task.options) - {"gate"} <= set(PHRASES)


# ── endpoint ────────────────────────────────────────────────────────────────

def test_cloze_uses_only_words_with_a_usable_sentence(client, db_factory):
    _register_and_login(client, "cloze1@example.com")
    category_id = _seed(client, db_factory, "cloze1@example.com", AIRPORT)

    res = _start(client, category_id)

    assert res.status_code == 200, res.text
    items = {item["original_word"]: item for item in res.json()}
    assert set(items) == {"gate", "delay", "travel"}

    travel = items["travel"]
    assert (travel["sentence_before"], travel["sentence_hidden"], travel["sentence_after"]) == \
        ("We ", "travelled", " to Italy.")
    assert travel["sentence_translation"] == "preklad: We travelled to Italy."
    # Slová bez vety sa do úlohy nedostanú, ale ako nesprávne možnosti slúžia.
    assert travel["answer"] == "travel"
    assert "travel" in travel["options"] and len(travel["options"]) == BLANK_OPTIONS
    assert set(travel["options"]) <= {w[0] for w in AIRPORT}


def test_cloze_respects_the_level_filter(client, db_factory):
    _register_and_login(client, "cloze2@example.com")
    category_id = _seed(client, db_factory, "cloze2@example.com", AIRPORT)

    known = _start(client, category_id, levels=("know",)).json()
    unknown = _start(client, category_id, levels=("dont_know", "learning")).json()

    assert [item["original_word"] for item in known] == ["delay"]
    assert {item["original_word"] for item in unknown} == {"gate", "travel"}


def test_cloze_is_empty_for_a_set_without_sentences(client, db_factory):
    _register_and_login(client, "cloze3@example.com")
    category_id = _seed(client, db_factory, "cloze3@example.com", [
        ("gate", "brána", None, KnowledgeLevel.DONT_KNOW),
        ("delay", "meškanie", None, KnowledgeLevel.DONT_KNOW),
    ])

    assert _start(client, category_id).json() == []


def test_cloze_works_on_a_set_of_phrases_without_any_sentences(client, db_factory):
    """Sada dialógov bez príkladových viet — presne tá, na ktorej dopĺňanie
    ukázalo „žiadne slovíčko nemá príkladovú vetu"."""
    _register_and_login(client, "cloze10@example.com")
    category_id = _seed(client, db_factory, "cloze10@example.com", [
        (phrase, f"preklad {n}", None, KnowledgeLevel.DONT_KNOW) for n, phrase in enumerate(PHRASES)])

    items = _start(client, category_id).json()

    assert sorted(item["original_word"] for item in items) == sorted(PHRASES)
    for item in items:
        assert item["sentence_before"] + item["sentence_hidden"] + item["sentence_after"] == item["original_word"]
        assert item["answer"] == item["sentence_hidden"] and item["answer"] in item["options"]
        assert item["sentence_translation"].startswith("preklad ")
        assert len(item["options"]) >= 2


def test_cloze_is_empty_when_the_set_has_a_single_word(client, db_factory):
    """Výber z jednej možnosti nie je úloha."""
    _register_and_login(client, "cloze4@example.com")
    category_id = _seed(client, db_factory, "cloze4@example.com", [
        ("gate", "brána", "The gate is closed.", KnowledgeLevel.DONT_KNOW)])

    assert _start(client, category_id).json() == []


def test_cloze_refuses_someone_elses_set(client, db_factory):
    _register_and_login(client, "cloze5@example.com")
    category_id = _seed(client, db_factory, "cloze5@example.com", AIRPORT)

    _register_and_login(client, "cloze5b@example.com")

    assert _start(client, category_id).status_code == 404
    assert _start(client, 999999).status_code == 404


def test_cloze_without_a_set_draws_options_from_the_words_own_set(client, db_factory):
    """Test „všetky slová": možnosti nesmú miešať sady (iný jazyk, iná téma)."""
    _register_and_login(client, "cloze6@example.com")
    _seed(client, db_factory, "cloze6@example.com", AIRPORT, name="Letisko")
    _seed(client, db_factory, "cloze6@example.com", [
        ("Hund", "pes", "Der Hund schläft.", KnowledgeLevel.DONT_KNOW),
        ("Katze", "mačka", "Die Katze trinkt Milch.", KnowledgeLevel.DONT_KNOW),
    ], name="Nemčina")

    items = {item["original_word"]: item for item in client.post(
        "/api/v1/words/cloze/start",
        json={"knowledge_levels": ["dont_know", "know"], "limit": 1000}).json()}

    assert sorted(items["Hund"]["options"]) == ["Hund", "Katze"]
    assert not {"Hund", "Katze"} & set(items["gate"]["options"])


def test_cloze_answers_are_saved_like_flashcard_answers(client, db_factory):
    _register_and_login(client, "cloze7@example.com")
    category_id = _seed(client, db_factory, "cloze7@example.com", AIRPORT)
    gate = next(i for i in _start(client, category_id).json() if i["original_word"] == "gate")

    res = client.post("/api/v1/words/test/submit", json=[{"word_id": gate["id"], "is_correct": True}])

    assert res.status_code == 200
    db = db_factory()
    try:
        word = db.query(Word).filter(Word.id == gate["id"]).one()
        assert word.knowledge_level == KnowledgeLevel.KNOW and word.times_tested == 1
    finally:
        db.close()


# ── stránky ─────────────────────────────────────────────────────────────────

def test_test_page_carries_the_cloze_mode(client):
    _register_and_login(client, "cloze8@example.com")

    page = client.get("/test?mode=cloze").text
    script = client.get("/static/js/page-flashcard_test.js").text

    assert 'id="clozeOptions"' in page and 'id="clozeNext"' in page
    assert "/api/v1/words/cloze/start" in script
    assert "_q.get('mode') === 'cloze'" in script
    # Možnosti sú slová z databázy — nesmú ísť do stránky cez innerHTML.
    body = script[script.index("function showClozeCard"):script.index("function chooseOption")]
    assert "innerHTML =" not in body and "createTextNode(option)" in body


def test_set_page_links_to_the_cloze_mode(client, db_factory):
    _register_and_login(client, "cloze9@example.com")
    category_id = _seed(client, db_factory, "cloze9@example.com", AIRPORT)

    page = client.get(f"/category/{category_id}/words").text

    assert f"/test?category={category_id}&mode=cloze&level=dont_know" in page
    assert f'/test?category={category_id}&mode=cloze"' in page

    # Sada, z ktorej úlohu spraviť nejde, nesmie viesť na prázdnu obrazovku:
    # skript voľby vymení za tlačidlo, ktoré vety doplní.
    assert 'id="clozeBlocked"' in page and 'id="clozeFillBtn"' in page
    script = client.get("/static/js/page-category_words.js").text
    assert "function renderClozeTile" in script and "renderClozeTile();" in script
