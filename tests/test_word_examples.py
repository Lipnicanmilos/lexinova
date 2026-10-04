"""Príkladové vety pri slovíčkach.

Veta vzniká dvoma cestami: AI ju vráti spolu so slovom pri tvorbe sady z témy,
alebo sa dogeneruje k slovám, ktoré ju nemajú (ručne pridané, importované,
staršie sady). V oboch prípadoch je nepovinná — slovo bez vety musí fungovať
presne ako doteraz.
"""
import pytest

from app.models.category import Category
from app.models.user import User
from app.models.word import EXAMPLE_MAX_LENGTH, Word, clean_example
from app.services.ai_category_service import (
    EXAMPLES_BATCH_SIZE,
    EXAMPLES_INLINE_MAX_COUNT,
    _build_examples_prompt,
    _build_prompt,
)
from app.services.limits import AI_DAILY_LIMIT_FREE


def _register_and_login(client, email):
    client.post("/api/v1/register", json={"email": email, "password": "Abcdef12"})
    client.post("/api/v1/login", json={"email": email, "password": "Abcdef12"})


def _user(db_factory, email):
    db = db_factory()
    try:
        return db.query(User).filter(User.email == email).one()
    finally:
        db.close()


def _category_with_words(client, db_factory, email, words, name="Vety"):
    """Sada so slovami; `words` sú dvojice alebo trojice (slovo, preklad[, veta])."""
    user_id = _user(db_factory, email).id
    res = client.post("/api/v1/categories", json={"name": name, "description": "", "user_id": user_id})
    assert res.status_code == 200, res.text
    category_id = res.json()["id"]
    for original, translation, *example in words:
        res = client.post("/api/v1/words", json={
            "original_word": original, "translation": translation, "category_id": category_id,
            "example_sentence": example[0] if example else None,
        })
        assert res.status_code == 200, res.text
    return category_id


def _words(client, category_id):
    return {w["original_word"]: w
            for w in client.get(f"/api/v1/words?category_id={category_id}").json()["words"]}


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


@pytest.fixture
def fake_examples(monkeypatch):
    """AI na dopĺňanie viet: vráti vetu ku každému slovu z dávky."""
    calls = []

    async def _fake(*, words, **kwargs):
        calls.append(words)
        return {w["id"]: {"example_sentence": f"I see the {w['original_word']}.",
                          "example_translation": f"Vidím {w['translation']}."}
                for w in words}

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("app.routers.categories.generate_word_examples", _fake)
    return calls


# ── prompt ──────────────────────────────────────────────────────────────────

def test_prompt_asks_for_sentences_only_for_small_sets():
    """Veta strojnásobí výstup na slovo — pri veľkej sade by sa odpoveď
    nezmestila do limitu Groq a Gemini by prešvihlo timeout."""
    small = _build_prompt("letisko", "en", "sk", EXAMPLES_INLINE_MAX_COUNT)
    large = _build_prompt("letisko", "en", "sk", EXAMPLES_INLINE_MAX_COUNT + 1)

    assert "example_sentence" in small and "example_translation" in small
    assert "example_sentence" not in large


def test_examples_prompt_carries_ids_and_meanings():
    prompt = _build_examples_prompt(
        [{"id": 7, "original_word": "gate", "translation": "brána"}], "en", "sk")

    assert '{"id":7,"word":"gate","meaning":"brána"}' in prompt


def test_clean_example_trims_clamps_and_rejects_junk():
    assert clean_example("  We  travel\na lot. ") == "We travel a lot."
    assert clean_example("") is None and clean_example("   ") is None
    assert clean_example(None) is None and clean_example(42) is None
    assert len(clean_example("a" * 1000)) == EXAMPLE_MAX_LENGTH


# ── tvorba sady z témy ──────────────────────────────────────────────────────

def test_ai_sentences_survive_preview_and_save(client, monkeypatch):
    _register_and_login(client, "ex1@example.com")

    async def _fake(**kwargs):
        return {"category_name": "Letisko", "words": [
            {"original_word": "gate", "translation": "brána",
             "example_sentence": "The gate is closed.", "example_translation": "Brána je zatvorená."},
            # Preklad bez vety nemá čo prekladať — nesmie sa uložiť osamote.
            {"original_word": "delay", "translation": "meškanie",
             "example_sentence": "", "example_translation": "Osamotený preklad."},
        ]}

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("app.routers.categories.generate_category_and_words_gemini", _fake)

    preview = client.post("/api/v1/categories/ai-preview", json={"prompt": "letisko"}).json()
    assert preview["words"][0]["example_sentence"] == "The gate is closed."

    saved = client.post("/api/v1/categories/ai-save", json={
        "category_name": preview["category_name"], "words": preview["words"]})
    assert saved.status_code == 200, saved.text

    words = _words(client, saved.json()["category_id"])
    assert words["gate"]["example_sentence"] == "The gate is closed."
    assert words["gate"]["example_translation"] == "Brána je zatvorená."
    assert words["delay"]["example_sentence"] is None
    assert words["delay"]["example_translation"] is None


# ── slovo ───────────────────────────────────────────────────────────────────

def test_sentence_is_not_swapped_in_reverse_test(client, db_factory):
    """V smere Preklad → Originál sa prehadzuje slovo s prekladom; veta ostáva
    v jazyku slova, inak by ju kartička čítala nesprávnym hlasom."""
    _register_and_login(client, "ex2@example.com")
    category_id = _category_with_words(
        client, db_factory, "ex2@example.com", [("gate", "brána", "The gate is closed.")])

    card = client.post("/api/v1/words/test/start", json={
        "category_id": category_id, "knowledge_levels": ["dont_know"],
        "test_direction": "translation_to_original"}).json()[0]

    assert card["original_word"] == "brána" and card["translation"] == "gate"
    assert card["example_sentence"] == "The gate is closed."


def test_edit_sets_and_clears_the_sentence(client, db_factory):
    _register_and_login(client, "ex3@example.com")
    category_id = _category_with_words(client, db_factory, "ex3@example.com", [("gate", "brána")])
    word_id = _words(client, category_id)["gate"]["id"]

    client.put(f"/api/v1/words/{word_id}", json={
        "example_sentence": "The gate is closed.", "example_translation": "Brána je zatvorená."})
    assert _words(client, category_id)["gate"]["example_sentence"] == "The gate is closed."

    # Úprava bez vety (staršia položka z offline fronty) ju nechá tak…
    client.put(f"/api/v1/words/{word_id}", json={"translation": "brána, východ"})
    assert _words(client, category_id)["gate"]["example_sentence"] == "The gate is closed."

    # …vyprázdnené pole ju zmaže.
    client.put(f"/api/v1/words/{word_id}", json={"example_sentence": "", "example_translation": ""})
    word = _words(client, category_id)["gate"]
    assert word["example_sentence"] is None and word["example_translation"] is None


def test_shared_set_is_imported_with_sentences(client, db_factory):
    _register_and_login(client, "ex4@example.com")
    category_id = _category_with_words(
        client, db_factory, "ex4@example.com", [("gate", "brána", "The gate is closed.")])
    code = client.post(f"/api/v1/categories/{category_id}/share").json()["share_code"]

    _register_and_login(client, "ex4b@example.com")
    imported = client.post("/api/v1/categories/import-shared", json={"share_code": code})
    assert imported.status_code == 200, imported.text

    words = _words(client, imported.json()["category_id"])
    assert words["gate"]["example_sentence"] == "The gate is closed."


# ── dopĺňanie viet k existujúcim slovám ─────────────────────────────────────

def test_fill_adds_sentences_only_where_missing(client, db_factory, fake_examples):
    _register_and_login(client, "ex5@example.com")
    category_id = _category_with_words(client, db_factory, "ex5@example.com", [
        ("gate", "brána"), ("delay", "meškanie"), ("ticket", "lístok", "My own sentence."),
    ])

    res = client.post(f"/api/v1/categories/{category_id}/ai-examples")

    assert res.status_code == 200, res.text
    assert res.json() == {"filled": 2, "remaining": 0}
    assert [w["original_word"] for w in fake_examples[0]] == ["gate", "delay"]
    words = _words(client, category_id)
    assert words["gate"]["example_sentence"] == "I see the gate."
    assert words["gate"]["example_translation"] == "Vidím brána."
    assert words["ticket"]["example_sentence"] == "My own sentence.", "vlastná veta sa neprepisuje"
    assert _user(db_factory, "ex5@example.com").ai_uses_count == 1


def test_fill_does_nothing_when_all_words_have_sentences(client, db_factory, fake_examples):
    """Žiadne volanie AI a žiadny odpočet z denného limitu."""
    _register_and_login(client, "ex6@example.com")
    category_id = _category_with_words(
        client, db_factory, "ex6@example.com", [("gate", "brána", "The gate is closed.")])

    res = client.post(f"/api/v1/categories/{category_id}/ai-examples")

    assert res.json() == {"filled": 0, "remaining": 0}
    assert not fake_examples
    assert not _user(db_factory, "ex6@example.com").ai_uses_count


def test_fill_works_in_batches(client, db_factory, fake_examples):
    _register_and_login(client, "ex7@example.com")
    user_id = _user(db_factory, "ex7@example.com").id
    category_id = client.post(
        "/api/v1/categories", json={"name": "Veľká", "description": "", "user_id": user_id}).json()["id"]
    # Priamo do databázy — Free účet má cez API strop 30 slov na sadu.
    db = db_factory()
    try:
        db.add_all([Word(original_word=f"word{i}", translation=f"slovo{i}",
                         category_id=category_id, user_id=user_id)
                    for i in range(EXAMPLES_BATCH_SIZE + 5)])
        db.commit()
    finally:
        db.close()

    first = client.post(f"/api/v1/categories/{category_id}/ai-examples").json()
    second = client.post(f"/api/v1/categories/{category_id}/ai-examples").json()

    assert first == {"filled": EXAMPLES_BATCH_SIZE, "remaining": 5}
    assert second == {"filled": 5, "remaining": 0}


def test_fill_ignores_other_users_set(client, db_factory, fake_examples):
    _register_and_login(client, "ex8@example.com")
    category_id = _category_with_words(client, db_factory, "ex8@example.com", [("gate", "brána")])

    _register_and_login(client, "ex8b@example.com")
    res = client.post(f"/api/v1/categories/{category_id}/ai-examples")

    assert res.json() == {"filled": 0, "remaining": 0}
    assert not fake_examples


def test_fill_refunds_quota_when_ai_fails(client, db_factory, monkeypatch):
    _register_and_login(client, "ex9@example.com")
    category_id = _category_with_words(client, db_factory, "ex9@example.com", [("gate", "brána")])

    async def _boom(**kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("app.routers.categories.generate_word_examples", _boom)

    res = client.post(f"/api/v1/categories/{category_id}/ai-examples")

    assert res.status_code == 502
    assert _user(db_factory, "ex9@example.com").ai_uses_count == 0
    assert _words(client, category_id)["gate"]["example_sentence"] is None


def test_fill_respects_daily_ai_limit(client, db_factory, fake_examples):
    _register_and_login(client, "ex10@example.com")
    category_id = _category_with_words(client, db_factory, "ex10@example.com", [("gate", "brána")])
    db = db_factory()
    try:
        from app.utils import utcnow
        user = db.query(User).filter(User.email == "ex10@example.com").one()
        user.ai_uses_date = utcnow().date()
        user.ai_uses_count = AI_DAILY_LIMIT_FREE
        db.commit()
    finally:
        db.close()

    res = client.post(f"/api/v1/categories/{category_id}/ai-examples")

    assert res.status_code == 429
    assert not fake_examples


def test_service_drops_sentences_for_ids_outside_the_batch(monkeypatch):
    """Model si id občas vymyslí — veta k slovu mimo dávky sa zapísať nesmie."""
    import asyncio

    from app.services import ai_category_service as service

    async def _fake_gemini(**kwargs):
        return {"examples": [
            {"id": 1, "example_sentence": "The gate is closed.", "example_translation": "Brána je zatvorená."},
            {"id": "2", "example_sentence": "  "},          # prázdna veta
            {"id": 999, "example_sentence": "Not yours."},  # cudzie id
            {"id": "x", "example_sentence": "Broken id."},
            "nonsense",
        ]}

    monkeypatch.setattr(service, "_ask_gemini", _fake_gemini)

    examples = asyncio.run(service.generate_word_examples(
        provider="gemini", api_key="k", model="m", language_from="en", language_to="sk",
        words=[{"id": 1, "original_word": "gate", "translation": "brána"},
               {"id": 2, "original_word": "delay", "translation": "meškanie"}]))

    assert examples == {1: {"example_sentence": "The gate is closed.",
                            "example_translation": "Brána je zatvorená."}}


# ── stránky ─────────────────────────────────────────────────────────────────

def test_flashcard_shows_sentence_inside_the_revealed_side(client, db_factory):
    """Veta musí byť v bloku, ktorý sa ukáže až po otočení — v opačnom smere
    testu by na prednej strane prezradila odpoveď."""
    _register_and_login(client, "ex11@example.com")
    page = client.get("/test").text

    block = page.split('id="translationBlock"')[1].split('id="flipHint"')[0]
    assert 'id="exampleBlock"' in block
    assert "example_sentence" in client.get("/static/js/page-flashcard_test.js").text


def test_set_page_loads_the_whole_set_not_the_first_hundred(client):
    """API bez limitu vráti 100 slov. Sada s 228 slovami tak mala v zozname
    len prvú stovku a tlačidlo hlásilo „Doplniť príkladové vety (100)"."""
    script = client.get("/static/js/page-category_words.js").text

    assert "WORDS_FETCH_LIMIT = 1000" in script
    assert "&limit=${WORDS_FETCH_LIMIT}" in script


def test_set_page_offers_fill_only_to_the_owner(client, db_factory):
    _register_and_login(client, "ex12@example.com")
    category_id = _category_with_words(client, db_factory, "ex12@example.com", [("gate", "brána")])

    page = client.get(f"/category/{category_id}/words").text

    assert 'id="examplesFill"' in page and 'id="editExample"' in page
    assert "/ai-examples" in client.get("/static/js/page-category_words.js").text
