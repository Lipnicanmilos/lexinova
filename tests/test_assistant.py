"""Lexi na nástenke (`POST /api/v1/assistant/command`).

Strážime, že pokyn skončí jednou bezpečnou akciou: id sady patrí používateľovi
(AI si ho mohla vymyslieť), čísla a jazyky sú v medziach, nezrozumiteľná
odpoveď AI je `clarify` — a že endpoint nič nevytvára. AI je mockovaná.
"""
import json

import pytest

from app.models.category import Category
from app.models.user import User
from app.services import assistant_service, tutor_service

PASSWORD = "Abcdef12"


def _login(client, db_factory, email, *, plus=True, pseudonymous=False):
    client.post("/api/v1/register", json={"email": email, "password": PASSWORD})
    client.post("/api/v1/login", json={"email": email, "password": PASSWORD})
    db = db_factory()
    try:
        user = db.query(User).filter(User.email == email).one()
        user.is_plus = plus
        user.is_pseudonymous = pseudonymous
        db.commit()
        return user.id
    finally:
        db.close()


def _make_set(db_factory, user_id, name):
    db = db_factory()
    try:
        category = Category(name=name, user_id=user_id)
        db.add(category)
        db.commit()
        return category.id
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _clean(db_factory):
    yield
    db = db_factory()
    try:
        db.query(Category).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture
def ai(monkeypatch):
    """AI vráti pripravený JSON; zapisuje si, čo dostala."""
    calls = []
    answer = {"value": {}}

    async def _ask(**kwargs):
        calls.append(kwargs)
        return json.dumps(answer["value"])

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(tutor_service, "_ask", _ask)
    return {"calls": calls, "answer": answer}


def _command(client, text, **extra):
    return client.post("/api/v1/assistant/command", json={"text": text, **extra})


def test_create_set_is_only_a_proposal(client, db_factory, ai):
    user_id = _login(client, db_factory, "lexi-create@example.com")
    ai["answer"]["value"] = {"action": "create_set", "reply": "Pripravím ti 20 slovíčok o letisku.",
                             "topic": "airport, A2", "count": 500, "language_from": "xx", "language_to": "sk"}
    res = _command(client, "sprav mi slovíčka o letisku")
    assert res.status_code == 200
    body = res.json()
    assert body["action"] == "create_set" and body["topic"] == "airport, A2"
    # Počet a jazyk z AI sa orežú na to, čo appka vie.
    assert body["count"] == assistant_service.COUNT_MAX and body["language_from"] == "en"
    # Endpoint nič neuložil — sada vznikne až cez /ai-save po potvrdení.
    db = db_factory()
    try:
        assert db.query(Category).filter(Category.user_id == user_id).count() == 0
    finally:
        db.close()


def test_practice_maps_to_own_set_and_lists_sets_for_ai(client, db_factory, ai):
    user_id = _login(client, db_factory, "lexi-practice@example.com")
    set_id = _make_set(db_factory, user_id, "12 lesson")
    ai["answer"]["value"] = {"action": "practice", "reply": "Ideme na test.", "set_id": set_id}

    body = _command(client, "precvič ma z lesson 12").json()
    assert body == {"action": "practice", "reply": "Ideme na test.",
                    "set": {"id": set_id, "name": "12 lesson"}, "url": f"/ucenie?category={set_id}"}
    prompt = ai["calls"][0]["system"][0]
    assert f"- {set_id}: 12 lesson" in prompt and "Slovak" in prompt
    assert ai["calls"][0]["opening_turn"] == "precvič ma z lesson 12"


def test_invented_or_foreign_set_id_becomes_clarify(client, db_factory, ai):
    owner_id = _login(client, db_factory, "lexi-owner@example.com")
    foreign = _make_set(db_factory, owner_id, "Cudzia sada")
    client.post("/api/v1/logout")
    _login(client, db_factory, "lexi-other@example.com")

    ai["answer"]["value"] = {"action": "practice", "reply": "Ktorú sadu?", "set_id": foreign}
    assert _command(client, "precvič ma z cudzej sady").json()["action"] == "clarify"
    # Cudzia sada sa AI ani neukáže.
    assert "Cudzia sada" not in ai["calls"][0]["system"][0]


def test_talk_with_and_without_set(client, db_factory, ai):
    user_id = _login(client, db_factory, "lexi-talk@example.com")
    set_id = _make_set(db_factory, user_id, "Letisko")
    ai["answer"]["value"] = {"action": "talk", "reply": "Poďme!", "set_id": None}
    assert _command(client, "poďme sa rozprávať").json()["url"] == "/tutor"
    ai["answer"]["value"] = {"action": "talk", "reply": "Poďme!", "set_id": set_id}
    assert _command(client, "porozprávajme sa o letisku").json()["url"] == f"/tutor?set={set_id}"


def test_garbage_from_ai_is_clarify():
    assert assistant_service.normalize("nope", [])["action"] == "clarify"
    assert assistant_service.normalize({"action": "delete_everything"}, [])["action"] == "clarify"
    assert assistant_service.normalize({"action": "create_set", "topic": "x"}, [])["action"] == "clarify"


def test_access_like_tutor(client, db_factory, ai):
    _login(client, db_factory, "lexi-free@example.com", plus=False)
    assert _command(client, "ahoj").status_code == 403
    client.post("/api/v1/logout")
    _login(client, db_factory, "lexi-kid@example.com", pseudonymous=True)
    assert _command(client, "ahoj").status_code == 403
    assert ai["calls"] == []


def test_ai_busy_is_429(client, db_factory, monkeypatch):
    _login(client, db_factory, "lexi-busy@example.com")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    async def _busy(**kwargs):
        raise tutor_service.GeminiRateLimited("busy")

    monkeypatch.setattr(tutor_service, "_ask", _busy)
    assert _command(client, "ahoj").status_code == 429


def test_commands_live_on_the_lexi_screen(client, db_factory):
    _login(client, db_factory, "lexi-screen@example.com")
    page = client.get("/tutor").text
    assert 'id="lexiForm"' in page and "/static/js/lexi-assistant.js" in page
    assert 'id="lexiForm"' not in client.get("/sady").text
    assert 'id="lexiForm"' not in client.get("/dashboard").text
