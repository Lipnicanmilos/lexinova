"""Listovanie: slová, ktoré človek nevie, na posúvanie.

Výber sa líši od učenia v jednom: berie aj slová, ktoré človek nevie, hoci majú
termín až zajtra. Inak by chyba z dnešného učenia nebola práve tam, kde ju hľadá.
"""
import io
from datetime import timedelta

from app.models.word import KnowledgeLevel, Word
from app.models.word_progress import WordProgress
from app.services.learning import FEED_SIZE
from app.utils import utcnow
from tests.test_learning import _class_with_set, _login, _set, _user


def _feed(client, **params):
    res = client.get("/api/v1/learn/feed", params=params)
    assert res.status_code == 200, res.text
    return res.json()


def _words(items):
    return sorted(item["original_word"] for item in items)


def test_feed_has_new_due_and_unknown_words_but_not_known_ones(client, db_factory):
    email = "feed-pick@example.com"
    _login(client, email)
    now = utcnow()
    db = db_factory()
    try:
        _set(db, _user(db, email).id, words=[
            ("new", "nové"),
            ("due", "na rade", {"box": 3, "due_at": now - timedelta(days=1), "knowledge_level": KnowledgeLevel.KNOW}),
            ("failed", "chyba", {"box": 1, "due_at": now + timedelta(days=1), "knowledge_level": KnowledgeLevel.DONT_KNOW}),
            ("known", "viem", {"box": 3, "due_at": now + timedelta(days=5), "knowledge_level": KnowledgeLevel.KNOW}),
        ])
    finally:
        db.close()

    assert _words(_feed(client)) == ["due", "failed", "new"]


def test_feed_items_have_no_exercise_to_solve(client, db_factory):
    email = "feed-item@example.com"
    _login(client, email)
    db = db_factory()
    try:
        _set(db, _user(db, email).id, words=[
            ("dog", "pes", {"example_sentence": "The dog barks.", "example_translation": "Pes šteká."}),
            ("cat", "mačka"), ("cow", "krava"), ("hen", "sliepka"), ("pig", "prasa"),
        ])
    finally:
        db.close()

    item = next(i for i in _feed(client) if i["original_word"] == "dog")
    assert item["translation"] == "pes"
    assert item["example_sentence"] == "The dog barks."
    assert item["example_translation"] == "Pes šteká."
    assert item["options"] == []


def test_feed_has_an_end(client, db_factory):
    email = "feed-size@example.com"
    _login(client, email)
    db = db_factory()
    try:
        _set(db, _user(db, email).id, words=[(f"w{i}", f"s{i}") for i in range(FEED_SIZE + 5)])
    finally:
        db.close()

    assert len(_feed(client)) == FEED_SIZE


def test_known_word_leaves_the_feed_until_it_is_due(client, db_factory):
    """Dvojité klepnutie ide cez /test/submit. Slovo pred termínom sa neposunie,
    ale z listovania zmizne."""
    email = "feed-know@example.com"
    _login(client, email)
    now = utcnow()
    db = db_factory()
    try:
        category_id = _set(db, _user(db, email).id, words=[
            ("failed", "chyba", {"box": 1, "due_at": now + timedelta(days=1), "knowledge_level": KnowledgeLevel.DONT_KNOW}),
            ("other", "iné"),
        ])
        word_id = db.query(Word.id).filter(Word.category_id == category_id, Word.original_word == "failed").scalar()
    finally:
        db.close()

    res = client.post("/api/v1/words/test/submit", json=[{"word_id": word_id, "is_correct": True}])
    assert res.status_code == 200
    assert _words(_feed(client)) == ["other"]

    db = db_factory()
    try:
        word = db.get(Word, word_id)
        assert word.box == 1
        assert word.due_at is not None
    finally:
        db.close()


def test_set_where_everything_is_known_stays_empty(client, db_factory):
    """Učenie by prešlo do učenia navyše. Listovanie je len o tom, čo nevieš."""
    email = "feed-empty@example.com"
    _login(client, email)
    now = utcnow()
    db = db_factory()
    try:
        category_id = _set(db, _user(db, email).id, words=[
            ("known", "viem", {"box": 3, "due_at": now + timedelta(days=5), "knowledge_level": KnowledgeLevel.KNOW}),
        ])
    finally:
        db.close()

    assert _feed(client, category_id=category_id) == []


def test_free_account_browses_only_the_unlocked_set(client, db_factory):
    email = "feed-lock@example.com"
    _login(client, email)
    now = utcnow()
    db = db_factory()
    try:
        user_id = _user(db, email).id
        locked = _set(db, user_id, "Stará", [("old", "staré")], created=now - timedelta(days=9))
        _set(db, user_id, "Nová", [("fresh", "čerstvé")], created=now)
    finally:
        db.close()

    assert _words(_feed(client)) == ["fresh"]
    assert client.get("/api/v1/learn/feed", params={"category_id": locked}).status_code == 403


def test_foreign_set_is_not_browsable(client, db_factory):
    email = "feed-owner@example.com"
    _login(client, email)
    db = db_factory()
    try:
        foreign = _set(db, _user(db, email).id, words=[("dog", "pes")])
    finally:
        db.close()

    _login(client, "feed-foreign@example.com")
    assert client.get("/api/v1/learn/feed", params={"category_id": foreign}).status_code == 404


def test_class_word_uses_the_students_own_progress(client, db_factory):
    email = "feed-student@example.com"
    _login(client, email)
    now = utcnow()
    db = db_factory()
    try:
        student_id = _user(db, email).id
        _class_with_set(db, student_id, [("unknown", "neviem"), ("known", "viem")])
        known_id = db.query(Word.id).filter(Word.original_word == "known").order_by(Word.id.desc()).first()[0]
        db.add(WordProgress(
            user_id=student_id, word_id=known_id, box=3,
            due_at=now + timedelta(days=5), knowledge_level=KnowledgeLevel.KNOW,
        ))
        db.commit()
    finally:
        db.close()

    assert _words(_feed(client)) == ["unknown"]


def test_page_needs_login(client):
    client.post("/api/v1/logout")
    res = client.get("/listovanie", follow_redirects=False)
    assert res.status_code in (302, 303)
    assert res.headers["location"] == "/login"


def test_page_has_no_tabs(client):
    _login(client, "feed-page@example.com")
    page = client.get("/listovanie").text
    assert "/static/js/page-feed.js" in page
    assert 'class="app-tabs"' not in page


def test_today_and_set_lead_to_the_feed(client, db_factory):
    email = "feed-link@example.com"
    _login(client, email)
    db = db_factory()
    try:
        category_id = _set(db, _user(db, email).id, words=[("dog", "pes")])
    finally:
        db.close()

    assert 'href="/listovanie"' in client.get("/dashboard").text
    page = client.get(f"/category/{category_id}/words").text
    assert f'href="/listovanie?category={category_id}"' in page
    assert f"/test?category={category_id}&level=dont_know" not in page


def test_scrolling_writes_nothing():
    """Keby posunutie rátalo ako „Neviem", prelistovanie by zhodilo slová na začiatok."""
    script = io.open("app/static/js/page-feed.js", encoding="utf-8").read()
    assert "is_correct: false" not in script
    assert "is_correct: true" in script


def test_known_words_cannot_be_lost():
    script = io.open("app/static/js/page-feed.js", encoding="utf-8").read()
    assert "sendBeacon" in script                     # zavretá karta, späť
    assert "visibilitychange" in script               # appka prepnutá do pozadia
    assert "answers.slice(pendingFrom)" in script     # nič sa nezapíše dvakrát
    assert "queueTestResults" in script               # výpadok siete
