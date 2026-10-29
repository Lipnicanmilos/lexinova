"""AI tútor s pamäťou (/tutor).

Strážime hlavne pamäť — že sa relácia po skončení zhrnie do profilu a spomienok,
že sa spomienky nájdu podľa významu a že ich používateľ vie zmazať — a prístup:
len PLUS/admin, nikdy žiacky účet, a s denným stropom (kvóta Gemini je spoločná).
Rozhovor vedie Gemini (záloha Groq, Claude len cez TUTOR_PROVIDER); AI je všade mockovaná.
"""
import asyncio

import pytest

from app.models.category import Category
from app.models.tutor import Embedding, TutorMemory, TutorMessage, TutorProfile, TutorSession
from app.models.user import User
from app.models.word import Word
from app.services import tutor_service as svc

PASSWORD = "Abcdef12"


def _register_and_login(client, email, *, plus=True, db_factory=None, pseudonymous=False):
    client.post("/api/v1/register", json={"email": email, "password": PASSWORD})
    client.post("/api/v1/login", json={"email": email, "password": PASSWORD})
    if db_factory is not None:
        db = db_factory()
        try:
            user = db.query(User).filter(User.email == email).one()
            user.is_plus = plus
            user.is_pseudonymous = pseudonymous
            db.commit()
            return user.id
        finally:
            db.close()


def _vector(*hot):
    """768-rozmerný vektor s jednotkami na zvolených pozíciách."""
    values = [0.0] * 768
    for index in hot:
        values[index] = 1.0
    return values


# Fake embedding: téma textu → smer vo vektorovom priestore.
TOPICS = {"football": 0, "work": 1, "holiday": 2}


async def _fake_embed(text, task="RETRIEVAL_DOCUMENT", timeout_s=8):
    hot = [i for word, i in TOPICS.items() if word in text.lower()]
    return _vector(*(hot or [10]))


@pytest.fixture(autouse=True)
def _clean(db_factory):
    yield
    db = db_factory()
    try:
        for model in (TutorMemory, TutorMessage, TutorSession, TutorProfile, Word, Category):
            db.query(model).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture
def ai(monkeypatch):
    """AI odpovedá číslovane, súhrn vracia pripravený JSON; všetko sa zapisuje."""
    calls = {"reply": [], "summary": []}
    summary = {
        "summary": "Talked about football and work. Struggles with past simple.",
        "facts": ["Name is Miloš", "Works in IT at a toll company", "Likes football"],
        "new_facts": ["Likes football"],
        "mistakes": ["Past simple of irregular verbs (goed -> went)"],
        "level": "B1",
        "new_words": [{"word": "referee", "translation": "rozhodca"},
                      {"word": "deadline", "translation": "termín"},
                      {"word": "", "translation": "prázdne"}],
    }

    async def _reply(**kwargs):
        calls["reply"].append(kwargs)
        n = len(calls["reply"])
        if kwargs["history"] and kwargs["history"][-1]["text"].startswith("I goed"):
            return "✔ I went to the match.\nNice! Who won?"
        return f"Reply {n}?"

    async def _summary(**kwargs):
        calls["summary"].append(kwargs)
        return dict(summary)

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(svc, "generate_reply", _reply)
    monkeypatch.setattr(svc, "summarize_session", _summary)
    monkeypatch.setattr(svc, "embed_text", _fake_embed)
    return calls


def _start(client, **body):
    return client.post("/api/v1/tutor/sessions", json=body)


def _say(client, session_id, text):
    return client.post(f"/api/v1/tutor/sessions/{session_id}/messages", json={"text": text})


# ── prístup ────────────────────────────────────────────────────────────────

def test_free_user_gets_reason_and_cannot_start(client, db_factory, ai):
    _register_and_login(client, "tutor-free@example.com", plus=False, db_factory=db_factory)

    state = client.get("/api/v1/tutor/state").json()
    assert state["available"] is False and "PLUS" in state["reason"]
    assert _start(client).status_code == 403
    assert ai["reply"] == []


def test_pseudonymous_account_never_gets_the_tutor(client, db_factory, ai):
    """Žiaci môžu byť deti — tútor si ukladá osobné údaje, aj keby mali PLUS."""
    _register_and_login(client, "tutor-kid@example.com", plus=True, db_factory=db_factory,
                        pseudonymous=True)
    assert _start(client).status_code == 403


def test_missing_ai_keys_is_503(client, db_factory, monkeypatch):
    for key in ("GEMINI_API_KEY", "GROQ_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.setenv(key, "")
    _register_and_login(client, "tutor-nokey@example.com", db_factory=db_factory)
    assert _start(client).status_code == 503
    assert client.get("/api/v1/tutor/state").json()["available"] is False


def test_logged_out_is_401(client, ai):
    client.post("/api/v1/logout")
    assert client.get("/api/v1/tutor/state").status_code == 401


# ── rozhovor ───────────────────────────────────────────────────────────────

def test_start_greets_and_stores_the_greeting(client, db_factory, ai):
    _register_and_login(client, "tutor-start@example.com", db_factory=db_factory)

    res = _start(client, level="B2", language_from="de")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["reply"] == "Reply 1?" and body["level"] == "B2" and body["language_from"] == "de"

    # Pokyny skladá server: jazyk a úroveň z profilu, pozdrav bez histórie.
    call = ai["reply"][0]
    assert call["history"] == []
    assert "German" in call["instructions"] and "B2" in call["instructions"]

    state = client.get("/api/v1/tutor/state").json()
    assert state["session"]["id"] == body["session_id"]
    assert state["session"]["messages"] == [{"role": "assistant", "text": "Reply 1?"}]


def test_message_returns_reply_and_separates_the_correction(client, db_factory, ai):
    _register_and_login(client, "tutor-msg@example.com", db_factory=db_factory)
    session_id = _start(client).json()["session_id"]

    res = _say(client, session_id, "I goed to the football match yesterday.")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["correction"] == "I went to the match."
    assert body["reply"] == "Nice! Who won?"

    # Claude dostal históriu z databázy: pozdrav + nová správa.
    history = ai["reply"][-1]["history"]
    assert [m["role"] for m in history] == ["assistant", "user"]

    db = db_factory()
    try:
        assert db.query(TutorMessage).filter(TutorMessage.session_id == session_id).count() == 3
        assert db.get(TutorSession, session_id).user_messages == 1
    finally:
        db.close()


def test_failed_ai_reply_stores_nothing(client, db_factory, ai, monkeypatch):
    _register_and_login(client, "tutor-fail@example.com", db_factory=db_factory)
    session_id = _start(client).json()["session_id"]

    async def _boom(**kwargs):
        raise RuntimeError("Claude down")

    monkeypatch.setattr(svc, "generate_reply", _boom)
    assert _say(client, session_id, "Hello").status_code == 502

    db = db_factory()
    try:
        # Len pozdrav — žiadna otázka bez odpovede, nič sa nezapočítalo.
        assert db.query(TutorMessage).filter(TutorMessage.session_id == session_id).count() == 1
        assert db.get(TutorSession, session_id).user_messages == 0
    finally:
        db.close()


def test_daily_limit(client, db_factory, ai, monkeypatch):
    monkeypatch.setenv("TUTOR_DAILY_MESSAGES", "1")
    _register_and_login(client, "tutor-limit@example.com", db_factory=db_factory)
    session_id = _start(client).json()["session_id"]

    first = _say(client, session_id, "One")
    assert first.status_code == 200 and first.json()["messages_left_today"] == 0
    assert _say(client, session_id, "Two").status_code == 429


def test_too_long_message_is_rejected(client, db_factory, ai):
    _register_and_login(client, "tutor-long@example.com", db_factory=db_factory)
    session_id = _start(client).json()["session_id"]
    assert _say(client, session_id, "x" * (svc.TUTOR_MESSAGE_MAX_LENGTH + 1)).status_code == 400


def test_someone_elses_session_is_404(client, db_factory, ai):
    _register_and_login(client, "tutor-owner@example.com", db_factory=db_factory)
    session_id = _start(client).json()["session_id"]

    client.post("/api/v1/logout")
    _register_and_login(client, "tutor-intruder@example.com", db_factory=db_factory)
    assert _say(client, session_id, "Hi").status_code == 404
    assert client.post(f"/api/v1/tutor/sessions/{session_id}/end").status_code == 404


# ── pamäť ──────────────────────────────────────────────────────────────────

def test_end_saves_summary_profile_memories_and_words(client, db_factory, ai):
    user_id = _register_and_login(client, "tutor-end@example.com", db_factory=db_factory)
    session_id = _start(client).json()["session_id"]
    _say(client, session_id, "I goed to the football match yesterday.")

    res = client.post(f"/api/v1/tutor/sessions/{session_id}/end")
    assert res.status_code == 200, res.text
    assert res.json()["words_added"] == 2 and res.json()["level"] == "B1"

    db = db_factory()
    try:
        profile = db.get(TutorProfile, user_id)
        assert "- Likes football" in profile.facts
        assert "goed -> went" in profile.mistakes
        assert profile.level == "B1" and profile.sessions_count == 1

        memories = db.query(TutorMemory).filter(TutorMemory.user_id == user_id).all()
        assert sorted(m.kind for m in memories) == ["fact", "summary"]
        assert all(len(m.embedding) == 768 for m in memories)

        category = db.query(Category).filter(Category.user_id == user_id).one()
        assert category.name == "AI tútor"
        assert sorted(w.original_word for w in category.words) == ["deadline", "referee"]
        assert db.get(TutorSession, session_id).ended_at is not None
    finally:
        db.close()

    # Druhé ukončenie nič nezopakuje.
    again = client.post(f"/api/v1/tutor/sessions/{session_id}/end").json()
    assert again["already_ended"] is True and len(ai["summary"]) == 1
    assert _say(client, session_id, "Hello?").status_code == 400


def test_session_without_user_messages_is_closed_without_summary(client, db_factory, ai):
    _register_and_login(client, "tutor-empty@example.com", db_factory=db_factory)
    session_id = _start(client).json()["session_id"]

    res = client.post(f"/api/v1/tutor/sessions/{session_id}/end")
    assert res.status_code == 200 and res.json()["summary"] is None
    assert ai["summary"] == []


def test_next_session_remembers_and_finds_memories_by_meaning(client, db_factory, ai):
    """Pamäť naprieč reláciami: súhrn ide do pozdravu, spomienka podľa významu
    k správe, ktorej sa týka."""
    _register_and_login(client, "tutor-remember@example.com", db_factory=db_factory)
    first = _start(client).json()["session_id"]
    _say(client, first, "I goed to the football match yesterday.")
    client.post(f"/api/v1/tutor/sessions/{first}/end")

    second = _start(client).json()["session_id"]
    greeting_notes = ai["reply"][-1]["notes"]
    assert "Talked about football and work" in greeting_notes
    assert "Likes football" in greeting_notes

    _say(client, second, "Did you watch football on Sunday?")
    notes = ai["reply"][-1]["notes"]
    # Fakt „Likes football" sa našiel podľa vektora (súhrn je v notes už z posledných relácií).
    assert "Older memories related" in notes and "(fact" in notes


def test_closed_without_ending_is_summarized_at_next_start(client, db_factory, ai):
    user_id = _register_and_login(client, "tutor-lazy@example.com", db_factory=db_factory)
    first = _start(client).json()["session_id"]
    _say(client, first, "I work in IT.")
    # Používateľ zavrel okno bez „Ukončiť".

    _start(client)
    assert len(ai["summary"]) == 1
    db = db_factory()
    try:
        assert db.get(TutorSession, first).summary
        assert db.get(TutorProfile, user_id).sessions_count == 1
    finally:
        db.close()


def test_failed_lazy_summary_does_not_block_new_session(client, db_factory, ai, monkeypatch):
    _register_and_login(client, "tutor-lazyfail@example.com", db_factory=db_factory)
    first = _start(client).json()["session_id"]
    _say(client, first, "Hello")

    async def _boom(**kwargs):
        raise RuntimeError("summary down")

    monkeypatch.setattr(svc, "summarize_session", _boom)
    res = _start(client)
    assert res.status_code == 200
    db = db_factory()
    try:
        # Uzavretá bez súhrnu — inak by sa za ňu platilo pri každom štarte.
        assert db.get(TutorSession, first).ended_at is not None
    finally:
        db.close()


def test_forget_everything(client, db_factory, ai):
    user_id = _register_and_login(client, "tutor-forget@example.com", db_factory=db_factory)
    session_id = _start(client).json()["session_id"]
    _say(client, session_id, "I like football.")
    client.post(f"/api/v1/tutor/sessions/{session_id}/end")

    assert client.delete("/api/v1/tutor/memory").status_code == 200
    db = db_factory()
    try:
        for model in (TutorMemory, TutorMessage, TutorSession):
            assert db.query(model).filter(model.user_id == user_id).count() == 0
        assert db.get(TutorProfile, user_id) is None
        # Sada so slovíčkami je bežná sada používateľa — ostáva.
        assert db.query(Category).filter(Category.user_id == user_id).count() == 1
    finally:
        db.close()


def test_account_deletion_removes_tutor_data(client, db_factory, ai):
    user_id = _register_and_login(client, "tutor-gdpr@example.com", db_factory=db_factory)
    session_id = _start(client).json()["session_id"]
    _say(client, session_id, "Hello")

    assert client.delete("/api/user").status_code == 200
    db = db_factory()
    try:
        assert db.query(TutorMessage).filter(TutorMessage.user_id == user_id).count() == 0
        assert db.query(TutorSession).filter(TutorSession.user_id == user_id).count() == 0
    finally:
        db.close()


# ── služba ─────────────────────────────────────────────────────────────────

def test_embedding_roundtrip_and_similarity_order(db_factory, client):
    db = db_factory()
    try:
        user_id = db.query(User).first().id if db.query(User).first() else None
        if user_id is None:
            user = User(email="tutor-vec@example.com", password="x")
            db.add(user)
            db.commit()
            user_id = user.id
        for kind, text, vec in [("fact", "work", _vector(1)), ("fact", "football", _vector(0)),
                                ("fact", "holiday", _vector(2)), ("fact", "no vector", None)]:
            db.add(TutorMemory(user_id=user_id, kind=kind, text=text, embedding=vec))
        db.commit()

        found = svc.find_relevant_memories(db, user_id, _vector(0), limit=2)
        assert [m.text for m in found][0] == "football"
        assert len(found) == 2
        assert svc.find_relevant_memories(db, user_id, None) == []
    finally:
        db.close()


def test_embedding_type_formats_for_postgres():
    assert Embedding().process_bind_param([0.5, 1, -0.25], None) == "[0.5,1,-0.25]"
    assert Embedding().process_result_value("[0.5,1]", None) == [0.5, 1.0]


def test_claude_messages_start_with_user_and_alternate():
    messages = svc._to_claude_messages([
        {"role": "assistant", "text": "Hi!"}, {"role": "user", "text": "Hello"},
        {"role": "user", "text": "again"},
    ], "(start)")
    assert messages[0]["role"] == "user"
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert messages[-1]["content"] == "Hello\nagain"


def test_split_reply_and_clean_reply():
    assert svc.split_reply("✔ I went.\nGreat!") == {"correction": "I went.", "reply": "Great!", "help": None}
    assert svc.split_reply("Great!") == {"correction": None, "reply": "Great!", "help": None}
    parts = svc.split_reply("Say: Can we speak Slovak?\nTry it!\nⓘ Povedz: Can we speak Slovak? – Môžeme hovoriť po slovensky?")
    assert parts["reply"] == "Say: Can we speak Slovak?\nTry it!"
    assert parts["help"] == "Povedz: Can we speak Slovak? – Môžeme hovoriť po slovensky?"
    # Všetko v pomoci → bublina by ostala prázdna, radšej celá odpoveď.
    assert svc.split_reply("ⓘ Len pomoc")["reply"] == "ⓘ Len pomoc"
    assert svc._clean_reply("**Hello** _there_") == "Hello there"


def test_instructions_allow_native_help_and_list_focus_words():
    profile = TutorProfile(user_id=1, level="A2", language_from="en", language_to="sk")
    plain = svc.build_instructions(profile)
    assert '"ⓘ "' in plain and "Slovak" in plain and "learner's set" not in plain
    focused = svc.build_instructions(profile, {"name": "12 lesson", "words": [
        {"word": "When did you go?", "translation": "Kedy si išiel?"}]})
    assert '"12 lesson"' in focused and "- When did you go? — Kedy si išiel?" in focused


# ── relácia nad sadou ──────────────────────────────────────────────────────

def _make_set(db_factory, user_id, name="12 lesson", language_from="en", words=3):
    db = db_factory()
    try:
        category = Category(name=name, user_id=user_id)
        db.add(category)
        db.flush()
        for i in range(words):
            db.add(Word(original_word=f"phrase {i}", translation=f"fráza {i}",
                        language_from=language_from, language_to="sk",
                        category_id=category.id, user_id=user_id))
        db.commit()
        return category.id
    finally:
        db.close()


def test_session_over_own_set_uses_its_words(client, db_factory, ai):
    user_id = _register_and_login(client, "tutor-set@example.com", db_factory=db_factory)
    set_id = _make_set(db_factory, user_id, language_from="de")

    state = client.get(f"/api/v1/tutor/state?set={set_id}").json()
    assert state["set"] == {"id": set_id, "name": "12 lesson"}

    res = _start(client, category_id=set_id, language_from="en")
    assert res.status_code == 200
    body = res.json()
    assert body["focus"]["name"] == "12 lesson" and len(body["focus"]["words"]) == 3
    # Rozhovor nad sadou je v jazyku jej slovíčok.
    assert body["language_from"] == "de"
    assert "- phrase 0 — fráza 0" in ai["reply"][0]["instructions"]

    _say(client, body["session_id"], "Hallo")
    assert "phrase 1" in ai["reply"][1]["instructions"]

    session = client.get("/api/v1/tutor/state").json()["session"]
    assert session["focus"]["category_id"] == set_id
    # Riadok so slovíčkami nie je správa — história ani AI ho nevidia.
    assert [m["role"] for m in session["messages"]] == ["assistant", "user", "assistant"]
    assert all(m["role"] != "focus" for m in ai["reply"][1]["history"])


def test_foreign_set_is_404(client, db_factory, ai):
    owner_id = _register_and_login(client, "tutor-owner@example.com", db_factory=db_factory)
    set_id = _make_set(db_factory, owner_id)
    client.post("/api/v1/logout")
    _register_and_login(client, "tutor-stranger@example.com", db_factory=db_factory)

    assert client.get(f"/api/v1/tutor/state?set={set_id}").json()["set"] is None
    assert _start(client, category_id=set_id).status_code == 404
    assert ai["reply"] == []


def test_help_line_comes_back_separately(client, db_factory, ai, monkeypatch):
    _register_and_login(client, "tutor-help@example.com", db_factory=db_factory)
    session_id = _start(client).json()["session_id"]

    async def _reply(**kwargs):
        return "You can say: Can we speak Slovak?\nⓘ Povedz: Can we speak Slovak? – Môžeme hovoriť po slovensky?"

    monkeypatch.setattr(svc, "generate_reply", _reply)
    body = _say(client, session_id, "môžeme hovoriť po slovensky").json()
    assert body["reply"] == "You can say: Can we speak Slovak?"
    assert body["help"].startswith("Povedz:")


# ── prepis reči ────────────────────────────────────────────────────────────

def _audio(client, data=b"OggS-fake-audio", content_type="audio/ogg;codecs=opus"):
    return client.post("/api/v1/tutor/transcribe", content=data, headers={"Content-Type": content_type})


def test_transcribe_returns_text_and_language(client, db_factory, ai, monkeypatch):
    _register_and_login(client, "tutor-stt@example.com", db_factory=db_factory)
    seen = {}

    async def _fake(data, mime):
        seen.update(data=data, mime=mime)
        return {"text": "ako sa povie obchod", "language": "sk"}

    monkeypatch.setattr(svc, "transcribe_audio", _fake)
    res = _audio(client)
    assert res.status_code == 200
    assert res.json() == {"text": "ako sa povie obchod", "language": "sk"}
    assert seen == {"data": b"OggS-fake-audio", "mime": "audio/ogg"}


def test_transcribe_rejects_bad_requests(client, db_factory, ai, monkeypatch):
    _register_and_login(client, "tutor-stt-bad@example.com", db_factory=db_factory)
    assert _audio(client, content_type="application/json").status_code == 415
    assert _audio(client, data=b"").status_code == 400
    monkeypatch.setattr(svc, "TUTOR_AUDIO_MAX_BYTES", 10)
    assert _audio(client, data=b"x" * 11).status_code == 413


def test_transcribe_needs_tutor_access(client, db_factory, ai):
    _register_and_login(client, "tutor-stt-free@example.com", plus=False, db_factory=db_factory)
    assert _audio(client).status_code == 403


def test_groq_transcription_drops_silence_and_maps_language(monkeypatch):
    sent = {}

    class _Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"text": "ignored", "language": "slovak", "segments": [
                {"text": " ako sa povie ", "no_speech_prob": 0.05},
                {"text": "Ďakujem za pozornosť.", "no_speech_prob": 0.9},
                {"text": " obchod", "no_speech_prob": 0.1},
            ]}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, files=None, data=None):
            sent.update(url=url, files=files, data=data)
            return _Response()

    monkeypatch.setenv("GROQ_API_KEY", "q")
    monkeypatch.setattr(svc.httpx, "AsyncClient", _Client)
    result = asyncio.run(svc.transcribe_audio(b"audio", "audio/webm"))
    assert result == {"text": "ako sa povie obchod", "language": "sk"}
    assert sent["files"]["file"][0] == "speech.webm"
    assert sent["data"]["response_format"] == "verbose_json"


def test_transcription_falls_back_to_gemini(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "q")
    monkeypatch.setenv("GEMINI_API_KEY", "g")

    async def _groq(data, mime):
        raise RuntimeError("down")

    async def _gemini(data, mime):
        return {"text": "hello", "language": "en"}

    monkeypatch.setattr(svc, "_transcribe_groq", _groq)
    monkeypatch.setattr(svc, "_transcribe_gemini", _gemini)
    assert asyncio.run(svc.transcribe_audio(b"a", "audio/ogg")) == {"text": "hello", "language": "en"}


def test_embed_text_without_key_is_none(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    assert asyncio.run(svc.embed_text("hello")) is None


def test_embed_text_sends_dimension_and_normalizes(monkeypatch):
    sent = {}

    class _Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"embedding": {"values": [3.0, 4.0] + [0.0] * 766}}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json):
            sent.update(url=url, json=json)
            return _Response()

    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(svc.httpx, "AsyncClient", _Client)
    vector = asyncio.run(svc.embed_text("hello", task="RETRIEVAL_QUERY"))
    assert sent["json"]["outputDimensionality"] == 768 and sent["json"]["taskType"] == "RETRIEVAL_QUERY"
    assert ":embedContent" in sent["url"]
    assert vector[:2] == pytest.approx([0.6, 0.8])


def test_summary_helpers_trim_ai_output():
    assert svc.as_bullets(["a", "", 3, "b"], max_items=5) == "- a\n- b"
    assert svc.as_bullets("nope", max_items=5) is None
    words = svc.clean_new_words([{"word": " big  deal ", "translation": "veľká vec"}, {"word": "x"}, "bad"])
    assert words == [{"word": "big deal", "translation": "veľká vec"}]



# ── kto odpovedá ───────────────────────────────────────────────────────────

def test_provider_chain_defaults_to_free_gemini(monkeypatch):
    """Claude API sa platí zvlášť (predplatné Pro ho nepokrýva) — bez výslovného
    TUTOR_PROVIDER=claude sa nepoužije, ani keď je kľúč nastavený."""
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("GROQ_API_KEY", "q")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.delenv("TUTOR_PROVIDER", raising=False)
    assert svc.provider_chain() == ["gemini", "groq"]
    monkeypatch.setenv("TUTOR_PROVIDER", "claude")
    assert svc.provider_chain() == ["claude", "gemini", "groq"]
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("TUTOR_PROVIDER", "gemini")
    assert svc.provider_chain() == ["gemini"]


def test_rate_limited_gemini_falls_back_to_groq(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("GROQ_API_KEY", "q")
    groq_calls = []

    async def _gemini(**kwargs):
        raise svc.GeminiRateLimited("busy")

    async def _groq(**kwargs):
        groq_calls.append(kwargs)
        return "Hi from Groq?"

    monkeypatch.setattr(svc.ai_chat_service, "_reply_gemini", _gemini)
    monkeypatch.setattr(svc.ai_chat_service, "_reply_groq", _groq)
    reply = asyncio.run(svc.generate_reply(instructions="I", notes="N", history=[]))
    assert reply == "Hi from Groq?"
    assert groq_calls[0]["system_prompt"] == "I\n\nN"
    assert groq_calls[0]["opening_turn"] == svc._OPENING_TURN


def test_all_providers_rate_limited_is_429(client, db_factory, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g")

    async def _gemini(**kwargs):
        raise svc.GeminiRateLimited("busy")

    monkeypatch.setattr(svc.ai_chat_service, "_reply_gemini", _gemini)
    _register_and_login(client, "tutor-busy@example.com", db_factory=db_factory)
    res = _start(client)
    assert res.status_code == 429 and "vyťažený" in res.json()["detail"]


def test_gemini_summary_asks_for_json(monkeypatch):
    """Súhrn ide do Gemini so system_instruction a JSON výstupom; história
    relácie je v pokynoch, nie v striedaní správ."""
    sent = {}

    class _Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": '{"summary": "We talked.", "level": "B1"}'}]}}]}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json):
            sent.update(url=url, json=json)
            return _Response()

    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(svc.ai_chat_service.httpx, "AsyncClient", _Client)
    profile = TutorProfile(user_id=1, level="A2", language_from="en", language_to="sk")
    data = asyncio.run(svc.summarize_session(
        profile=profile, history=[{"role": "user", "text": "I goed home"}]
    ))
    assert data["summary"] == "We talked."
    payload = sent["json"]
    assert ":generateContent" in sent["url"] and "/v1beta/" in sent["url"]
    assert payload["generationConfig"]["responseMimeType"] == "application/json"
    assert "I goed home" in payload["system_instruction"]["parts"][0]["text"]
    assert payload["contents"] == [{"role": "user", "parts": [{"text": svc._SUMMARY_TURN}]}]

# ── stránka ────────────────────────────────────────────────────────────────

def test_tutor_page_requires_login(client):
    client.post("/api/v1/logout")
    res = client.get("/tutor", follow_redirects=False)
    assert res.status_code == 303 and res.headers["location"] == "/login"


def test_tutor_page_renders_for_logged_in_user(client, db_factory):
    _register_and_login(client, "tutor-page@example.com", db_factory=db_factory)
    res = client.get("/tutor")
    assert res.status_code == 200
    assert 'id="tutorAvatar"' in res.text and "page-tutor.js" in res.text


def test_robots_hides_tutor(client):
    assert "Disallow: /tutor" in client.get("/robots.txt").text
