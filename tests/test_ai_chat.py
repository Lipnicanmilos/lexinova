"""Rozhovor s AI nad slovíčkami sady — okno na stránke sady.

Server si rozhovor nepamätá: klient posiela históriu a podpísaný lístok zo
štartu. Testy strážia hlavne to, čo z toho vyplýva — že lístok sa nedá
podvrhnúť ani preniesť, že pokyny pre AI skladá server zo slov v databáze
a že rozhovor má strop, takže sa okno nedá použiť ako neobmedzený chatbot.
AI je všade mockovaná.
"""
import asyncio

import pytest

from app.models.category import Category
from app.models.user import User
from app.models.word import KnowledgeLevel, Word
from app.services import ai_chat_service as service
from app.services.ai_chat_service import (
    CHAT_MAX_USER_MESSAGES,
    CHAT_MESSAGE_MAX_LENGTH,
    CHAT_WORDS,
    build_system_prompt,
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


def _seed(db_factory, email, words, name="Letisko"):
    """Sada so slovami; `words` sú (slovo, preklad, úroveň)."""
    db = db_factory()
    try:
        user_id = db.query(User).filter(User.email == email).one().id
        category = Category(name=name, description="", user_id=user_id)
        db.add(category)
        db.commit()
        db.add_all([Word(original_word=o, translation=t, category_id=category.id,
                         user_id=user_id, knowledge_level=level) for o, t, level in words])
        db.commit()
        return category.id
    finally:
        db.close()


AIRPORT = [
    ("gate", "brána", KnowledgeLevel.DONT_KNOW),
    ("delay", "meškanie", KnowledgeLevel.DONT_KNOW),
    ("ticket", "lístok", KnowledgeLevel.KNOW),
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


@pytest.fixture
def fake_ai(monkeypatch):
    """AI odpovie číslovanou otázkou a zapamätá si, s čím bola volaná."""
    calls = []

    async def _fake(**kwargs):
        calls.append(kwargs)
        return f"Question {len(calls)}?"

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("app.routers.ai_chat.generate_chat_reply", _fake)
    return calls


def _start(client, category_id, level="B1"):
    return client.post(f"/api/v1/categories/{category_id}/chat/start", json={"level": level})


def _reply(client, category_id, token, messages):
    return client.post(f"/api/v1/categories/{category_id}/chat/reply",
                       json={"token": token, "messages": messages})


def _history(turns):
    """História s `turns` správami používateľa: AI, ja, AI, ja…"""
    messages = []
    for n in range(turns):
        messages += [{"role": "assistant", "text": f"Question {n + 1}?"},
                     {"role": "user", "text": f"Answer {n + 1}."}]
    return messages


# ── pokyny pre AI ───────────────────────────────────────────────────────────

def test_system_prompt_carries_words_level_and_languages():
    prompt = build_system_prompt(
        [{"original_word": "gate", "translation": "brána"}], "B1", "en", "sk")

    assert "- gate — brána" in prompt
    assert "level is B1" in prompt and '"en"' in prompt and '"sk"' in prompt
    # Okno je cvičenie jazyka, nie všeobecný chatbot.
    assert "language practice only" in prompt


def test_gemini_gets_system_prompt_apart_from_the_alternating_history(monkeypatch):
    """Tvar požiadavky sa naživo otestovať nedá (lokálne nie je kľúč), tak aspoň
    to, čo Gemini vyžaduje: pokyny mimo histórie a rozhovor začínajúci „user"."""
    sent = {}

    class _Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "  How was your flight?  "}]}}]}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None, **kwargs):
            sent.update(url=url, payload=json)
            return _Response()

    monkeypatch.setattr("app.services.ai_chat_service.httpx.AsyncClient", _Client)

    reply = asyncio.run(service.generate_chat_reply(
        provider="gemini", api_key="k", model="gemini-2.5-flash",
        words=[{"original_word": "gate", "translation": "brána"}],
        level="A2", language_from="en", language_to="sk",
        messages=[{"role": "assistant", "text": "Where are you going?"},
                  {"role": "user", "text": "I go to Rome."}]))

    assert reply == "How was your flight?"
    assert "/v1beta/models/gemini-2.5-flash:generateContent" in sent["url"]
    assert "- gate — brána" in sent["payload"]["system_instruction"]["parts"][0]["text"]
    assert [c["role"] for c in sent["payload"]["contents"]] == ["user", "model", "user"]
    assert sent["payload"]["contents"][2]["parts"][0]["text"] == "I go to Rome."


def test_empty_ai_reply_is_a_failure_not_a_message(monkeypatch):
    async def _empty(**kwargs):
        return "   "

    monkeypatch.setattr(service, "_reply_gemini", _empty)

    with pytest.raises(RuntimeError):
        asyncio.run(service.generate_chat_reply(
            provider="gemini", api_key="k", model="m", words=[], level="A2",
            language_from="en", language_to="sk", messages=[]))


# ── začiatok rozhovoru ──────────────────────────────────────────────────────

def test_start_returns_first_question_words_and_charges_one_generation(client, db_factory, fake_ai):
    _register_and_login(client, "chat1@example.com")
    category_id = _seed(db_factory, "chat1@example.com", AIRPORT)

    res = _start(client, category_id)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["reply"] == "Question 1?" and body["messages_left"] == CHAT_MAX_USER_MESSAGES
    assert {w["original_word"] for w in body["words"]} == {"gate", "delay", "ticket"}
    assert fake_ai[0]["level"] == "B1" and fake_ai[0]["messages"] == []
    assert fake_ai[0]["language_from"] == "en" and fake_ai[0]["language_to"] == "sk"
    assert _user(db_factory, "chat1@example.com").ai_uses_count == 1


def test_start_prefers_words_the_user_does_not_know_yet(client, db_factory, fake_ai):
    _register_and_login(client, "chat2@example.com")
    words = [(f"known{i}", "x", KnowledgeLevel.KNOW) for i in range(CHAT_WORDS)]
    words += [(f"new{i}", "x", KnowledgeLevel.DONT_KNOW) for i in range(4)]
    category_id = _seed(db_factory, "chat2@example.com", words)

    picked = [w["original_word"] for w in _start(client, category_id).json()["words"]]

    assert len(picked) == CHAT_WORDS
    assert {f"new{i}" for i in range(4)} <= set(picked)


def test_start_rejects_unknown_level_empty_set_and_someone_elses_set(client, db_factory, fake_ai):
    _register_and_login(client, "chat3@example.com")
    category_id = _seed(db_factory, "chat3@example.com", AIRPORT)
    empty_id = _seed(db_factory, "chat3@example.com", [], name="Prázdna")

    assert _start(client, category_id, level="Z9").status_code == 422
    assert _start(client, empty_id).status_code == 404

    _register_and_login(client, "chat3b@example.com")
    assert _start(client, category_id).status_code == 404
    assert not fake_ai
    assert not _user(db_factory, "chat3@example.com").ai_uses_count


def test_start_refunds_the_generation_when_ai_fails(client, db_factory, monkeypatch):
    _register_and_login(client, "chat4@example.com")
    category_id = _seed(db_factory, "chat4@example.com", AIRPORT)

    async def _boom(**kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("app.routers.ai_chat.generate_chat_reply", _boom)

    assert _start(client, category_id).status_code == 502
    assert _user(db_factory, "chat4@example.com").ai_uses_count == 0


def test_start_respects_the_daily_ai_limit(client, db_factory, fake_ai):
    _register_and_login(client, "chat5@example.com")
    category_id = _seed(db_factory, "chat5@example.com", AIRPORT)
    db = db_factory()
    try:
        from app.utils import utcnow
        user = db.query(User).filter(User.email == "chat5@example.com").one()
        user.ai_uses_date = utcnow().date()
        user.ai_uses_count = AI_DAILY_LIMIT_FREE
        db.commit()
    finally:
        db.close()

    assert _start(client, category_id).status_code == 429
    assert not fake_ai


# ── pokračovanie ────────────────────────────────────────────────────────────

def test_reply_continues_with_the_words_and_level_from_the_start(client, db_factory, fake_ai):
    _register_and_login(client, "chat6@example.com")
    category_id = _seed(db_factory, "chat6@example.com", AIRPORT)
    token = _start(client, category_id, level="A1").json()["token"]

    res = _reply(client, category_id, token, _history(1))

    assert res.status_code == 200, res.text
    assert res.json() == {"reply": "Question 2?", "messages_left": CHAT_MAX_USER_MESSAGES - 1}
    call = fake_ai[1]
    assert call["level"] == "A1"
    assert {w["original_word"] for w in call["words"]} == {"gate", "delay", "ticket"}
    assert call["messages"][-1] == {"role": "user", "text": "Answer 1."}
    # Pokračovanie už denný limit neodpočítava.
    assert _user(db_factory, "chat6@example.com").ai_uses_count == 1


def test_reply_refuses_a_forged_or_borrowed_ticket(client, db_factory, fake_ai):
    _register_and_login(client, "chat7@example.com")
    category_id = _seed(db_factory, "chat7@example.com", AIRPORT)
    other_id = _seed(db_factory, "chat7@example.com", AIRPORT, name="Iná sada")
    token = _start(client, category_id).json()["token"]

    assert _reply(client, category_id, token + "x", _history(1)).status_code == 400
    assert _reply(client, category_id, "nonsense", _history(1)).status_code == 400
    # Lístok platí len pre sadu, pre ktorú bol vydaný…
    assert _reply(client, other_id, token, _history(1)).status_code == 400

    # …a len pre toho, komu bol vydaný.
    _register_and_login(client, "chat7b@example.com")
    assert _reply(client, category_id, token, _history(1)).status_code == 400
    assert len(fake_ai) == 1, "po štarte sa AI nesmela zavolať ani raz"


def test_reply_refuses_an_expired_ticket(client, db_factory, fake_ai, monkeypatch):
    _register_and_login(client, "chat8@example.com")
    category_id = _seed(db_factory, "chat8@example.com", AIRPORT)
    token = _start(client, category_id).json()["token"]

    monkeypatch.setattr("app.routers.ai_chat.CHAT_TOKEN_MAX_AGE_S", -1)

    res = _reply(client, category_id, token, _history(1))
    assert res.status_code == 400 and "vypršal" in res.json()["detail"]


def test_conversation_has_a_ceiling(client, db_factory, fake_ai):
    _register_and_login(client, "chat9@example.com")
    category_id = _seed(db_factory, "chat9@example.com", AIRPORT)
    token = _start(client, category_id).json()["token"]

    last = _reply(client, category_id, token, _history(CHAT_MAX_USER_MESSAGES))
    assert last.status_code == 200 and last.json()["messages_left"] == 0

    over = _reply(client, category_id, token, _history(CHAT_MAX_USER_MESSAGES + 1))
    assert over.status_code == 422, "dlhšiu históriu odmietne už schéma"


@pytest.mark.parametrize("messages", [
    [{"role": "user", "text": "Hi"}, {"role": "user", "text": "Hi again"}],           # nezačína AI
    [{"role": "assistant", "text": "Q?"}, {"role": "assistant", "text": "Q again?"}],  # nestrieda sa
    [{"role": "assistant", "text": "Q?"}, {"role": "user", "text": "A."},
     {"role": "assistant", "text": "Q2?"}],                                            # nekončí mnou
    [{"role": "assistant", "text": "Q?"}, {"role": "user", "text": "x" * (CHAT_MESSAGE_MAX_LENGTH + 1)}],
])
def test_reply_validates_the_history(client, db_factory, fake_ai, messages, request):
    # Vlastný účet na každý prípad: štyri štarty by jednému Free účtu minuli denný limit.
    email = f"chat10-{request.node.callspec.id}@example.com"
    _register_and_login(client, email)
    category_id = _seed(db_factory, email, AIRPORT)
    token = _start(client, category_id).json()["token"]

    assert _reply(client, category_id, token, messages).status_code in (400, 422)
    assert len(fake_ai) == 1


def test_reply_stops_when_the_words_were_deleted(client, db_factory, fake_ai):
    _register_and_login(client, "chat11@example.com")
    category_id = _seed(db_factory, "chat11@example.com", AIRPORT)
    token = _start(client, category_id).json()["token"]
    db = db_factory()
    try:
        db.query(Word).filter(Word.category_id == category_id).delete()
        db.commit()
    finally:
        db.close()

    res = _reply(client, category_id, token, _history(1))
    assert res.status_code == 400 and len(fake_ai) == 1


# ── stránka ─────────────────────────────────────────────────────────────────

def test_set_page_has_the_chat_window(client, db_factory):
    _register_and_login(client, "chat12@example.com")
    category_id = _seed(db_factory, "chat12@example.com", AIRPORT)

    page = client.get(f"/category/{category_id}/words").text
    script = client.get("/static/js/page-category_words.js").text

    assert 'onclick="openChat()"' in page and 'id="chatModal"' in page
    assert [level for level in ("A1", "A2", "B1", "B2", "C1") if f'data-level="{level}"' in page] == \
        ["A1", "A2", "B1", "B2", "C1"]
    assert "/chat/${path}" in script
    # Správy od AI aj od používateľa sú cudzí text — do stránky len cez textContent.
    body = script[script.index("function renderChat()"):script.index("function chatLanguage")]
    assert "innerHTML" not in body and "body.textContent = m.text" in body
    # Kopírovanie promptu rozhovor nahradil — nesmie ostať ani v stránke, ani v skripte.
    assert "copyChatPrompt" not in page and "copyChatPrompt" not in script
