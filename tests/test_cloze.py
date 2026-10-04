"""Dopĺňanie do viet — druhý režim obrazovky testu.

Úlohu pripravuje server: v príkladovej vete nájde slovo, vynechá ho a pridá
nesprávne možnosti z tej istej sady. Slovo, ktoré sa vo vete nenašlo, do úlohy
nejde — vynechať nesprávne miesto je horšie než mať o úlohu menej.
"""
import random

import pytest

from app.models.category import Category
from app.models.user import User
from app.models.word import KnowledgeLevel, Word
from app.services.cloze import BLANK_OPTIONS, pick_options, split_sentence


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
