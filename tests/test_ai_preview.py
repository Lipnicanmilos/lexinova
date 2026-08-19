"""Náhľad pred uložením — AI generuje návrh, do účtu ide až odsúhlasený výber.

Predtým sa vygenerovaná sada ukladala rovno; používateľ nemal kde vyhodiť
slová, ktoré nechce, ani premenovať kategóriu. AI volanie sa deje v náhľade
(tam vzniká náklad), uloženie je zadarmo.
"""
import pytest

from app.models.category import Category
from app.models.word import Word


def _register_and_login(client, email):
    client.post("/api/v1/register", json={"email": email, "password": "Abcdef12"})
    client.post("/api/v1/login", json={"email": email, "password": "Abcdef12"})


@pytest.fixture
def fake_ai(monkeypatch):
    """Gemini vráti pripravený návrh; kľúč musí existovať, inak sa provider preskočí."""
    calls = []

    async def _fake(**kwargs):
        calls.append(kwargs)
        return {
            "category_name": "Na letisku",
            "category_description": "Slovíčka na letisko",
            "words": [
                {"original_word": "gate", "translation": "brána"},
                {"original_word": "delay", "translation": "meškanie"},
                {"original_word": "Gate", "translation": "východ"},   # duplicita
            ],
        }

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("app.routers.categories.generate_category_and_words_gemini", _fake)
    return calls


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


def test_preview_returns_words_without_saving_anything(client, fake_ai, db_factory):
    _register_and_login(client, "preview1@example.com")

    res = client.post("/api/v1/categories/ai-preview",
                      json={"prompt": "letisko", "language_from": "en", "language_to": "sk", "count": 5})

    assert res.status_code == 200
    body = res.json()
    assert body["category_name"] == "Na letisku"
    assert len(fake_ai) == 1

    # Kontrola sa viaže na tohto používateľa — iné testy v behu majú vlastné dáta.
    db = db_factory()
    try:
        from app.models.user import User
        user = db.query(User).filter(User.email == "preview1@example.com").one()
        categories = db.query(Category).filter(Category.user_id == user.id).count()
        assert categories == 0, "náhľad nesmie nič uložiť"
        assert db.query(Word).filter(Word.user_id == user.id).count() == 0
    finally:
        db.close()


def test_preview_merges_duplicate_headwords(client, fake_ai):
    _register_and_login(client, "preview2@example.com")

    words = client.post("/api/v1/categories/ai-preview", json={"prompt": "letisko"}).json()["words"]

    originals = [w["original_word"] for w in words]
    assert originals == ["gate", "delay"], "v náhľade nemá svietiť to isté slovo dvakrát"
    assert words[0]["translation"] == "brána, východ"


def test_save_persists_only_the_selection_and_the_edited_name(client, db_factory):
    _register_and_login(client, "preview3@example.com")

    res = client.post("/api/v1/categories/ai-save", json={
        "category_name": "Letisko — moja sada",
        "category_description": "Slovíčka na letisko",
        "language_from": "en",
        "language_to": "sk",
        "words": [{"original_word": "gate", "translation": "brána",
                   "language_from": "en", "language_to": "sk"}],
    })

    assert res.status_code == 200
    assert res.json()["inserted_words"] == 1

    db = db_factory()
    try:
        category = db.query(Category).filter(Category.name == "Letisko — moja sada").one()
        words = db.query(Word).filter(Word.category_id == category.id).all()
        assert [w.original_word for w in words] == ["gate"]
    finally:
        db.close()


def test_save_without_words_is_rejected(client, db_factory):
    _register_and_login(client, "preview4@example.com")

    res = client.post("/api/v1/categories/ai-save", json={
        "category_name": "Prázdna", "words": [],
    })

    assert res.status_code == 422
    db = db_factory()
    try:
        assert db.query(Category).filter(Category.name == "Prázdna").count() == 0
    finally:
        db.close()


def test_save_does_not_call_ai(client, fake_ai):
    """Uloženie je zadarmo — druhé volanie AI by kvótu minulo dvakrát."""
    _register_and_login(client, "preview5@example.com")

    client.post("/api/v1/categories/ai-save", json={
        "category_name": "Letisko",
        "words": [{"original_word": "gate", "translation": "brána"}],
    })

    assert not fake_ai
