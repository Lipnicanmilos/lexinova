"""Opakovanie s rozostupmi a jedno učenie.

Predtým malo slovo dva stavy a jedno „Viem" platilo navždy, takže appka nevedela
povedať, čo sa učiť dnes. Teraz má slovo priehradku a termín a server skladá
dennú dávku naprieč sadami — so zámkom free účtu a so sadami tried.
"""
import random
from datetime import datetime, timedelta

import pytest
from sqlalchemy import event

from app.models.category import Category
from app.models.school_class import ClassCategory, ClassMember, SchoolClass
from app.models.user import User
from app.models.word import KnowledgeLevel, Word
from app.models.word_progress import WordProgress
from app.services.learning import CARD, CHOICE, CLOZE, LISTEN, SESSION_SIZE, pick_exercise
from app.services.srs import BOX_INTERVAL_DAYS, MAX_BOX, apply_answer, apply_manual_level
from app.utils import utcnow

NOW = datetime(2026, 11, 2, 8, 30)


def _login(client, email):
    client.post("/api/v1/register", json={"email": email, "password": "Abcdef12"})
    client.post("/api/v1/login", json={"email": email, "password": "Abcdef12"})


def _user(db, email):
    return db.query(User).filter(User.email == email).one()


def _set(db, user_id, name="Sada", words=(), created=None):
    category = Category(name=name, user_id=user_id, created_at=created or utcnow())
    db.add(category)
    db.flush()
    for spec in words:
        original, translation = spec[0], spec[1]
        extra = spec[2] if len(spec) > 2 else {}
        db.add(Word(original_word=original, translation=translation, category_id=category.id,
                    user_id=user_id, **extra))
    db.commit()
    return category.id


def _session(client, **params):
    res = client.get("/api/v1/learn/session", params=params)
    assert res.status_code == 200, res.text
    return res.json()


# ── priehradky ──

def test_correct_answer_moves_the_word_up_and_later():
    box, due = apply_answer(0, None, True, NOW)
    assert box == 1
    assert due == datetime(2026, 11, 3)

    box, due = apply_answer(box, due, True, datetime(2026, 11, 3, 9))
    assert box == 2
    assert due == datetime(2026, 11, 6)


def test_due_date_is_the_start_of_a_day():
    """Zopakované o ôsmej nesmie zajtra o siedmej čakať ešte hodinu."""
    _, due = apply_answer(0, None, True, datetime(2026, 11, 2, 23, 59))
    assert (due.hour, due.minute) == (0, 0)


def test_wrong_answer_comes_back_tomorrow_from_any_box():
    box, due = apply_answer(4, NOW - timedelta(days=1), False, NOW)
    assert box == 1
    assert due == datetime(2026, 11, 3)


def test_early_correct_answer_does_not_move_the_word():
    """Inak by sa slovo dalo za jeden večer vyklikať do poslednej priehradky."""
    due = NOW + timedelta(days=5)
    assert apply_answer(2, due, True, NOW) == (2, due)


def test_early_wrong_answer_still_counts():
    box, due = apply_answer(3, NOW + timedelta(days=5), False, NOW)
    assert box == 1
    assert due == datetime(2026, 11, 3)


def test_top_box_stays_on_top():
    box, due = apply_answer(MAX_BOX, NOW, True, NOW)
    assert box == MAX_BOX
    assert due == datetime(2026, 11, 2) + timedelta(days=BOX_INTERVAL_DAYS[MAX_BOX])


def test_manual_levels():
    assert apply_manual_level(0, True, NOW)[0] == 2
    assert apply_manual_level(4, True, NOW)[0] == 4
    assert apply_manual_level(4, False, NOW) == (1, NOW)


# ── zápis cez /test/submit ──

def test_submit_updates_box_and_due_date(client, db_factory):
    email = "srs-submit@example.com"
    _login(client, email)
    db = db_factory()
    try:
        user_id = _user(db, email).id
        _set(db, user_id, words=[("dog", "pes"), ("cat", "mačka")])
        ok, bad = db.query(Word).filter(Word.user_id == user_id).order_by(Word.id).all()
        ok_id, bad_id = ok.id, bad.id
    finally:
        db.close()

    res = client.post("/api/v1/words/test/submit", json=[
        {"word_id": ok_id, "is_correct": True}, {"word_id": bad_id, "is_correct": False},
    ])
    assert res.status_code == 200

    db = db_factory()
    try:
        ok, bad = db.get(Word, ok_id), db.get(Word, bad_id)
        assert ok.box == 1 and ok.due_at is not None
        assert bad.box == 1 and bad.due_at is not None
        assert ok.knowledge_level == KnowledgeLevel.KNOW
        assert bad.knowledge_level == KnowledgeLevel.DONT_KNOW
    finally:
        db.close()


def test_manual_level_change_sets_the_schedule(client, db_factory):
    email = "srs-manual@example.com"
    _login(client, email)
    db = db_factory()
    try:
        user_id = _user(db, email).id
        _set(db, user_id, words=[("dog", "pes")])
        word_id = db.query(Word).filter(Word.user_id == user_id).one().id
    finally:
        db.close()

    client.put(f"/api/v1/words/{word_id}/knowledge-level", json={"knowledge_level": "know"})
    db = db_factory()
    try:
        word = db.get(Word, word_id)
        assert word.box == 2
        assert word.due_at > utcnow()
    finally:
        db.close()


# ── denná dávka ──

def test_due_words_come_before_new_ones(client, db_factory):
    email = "srs-order@example.com"
    _login(client, email)
    db = db_factory()
    try:
        user_id = _user(db, email).id
        now = utcnow()
        _set(db, user_id, words=[
            ("new", "nové"),
            ("later", "neskôr", {"box": 2, "due_at": now + timedelta(days=2)}),
            ("recent", "nedávno", {"box": 1, "due_at": now - timedelta(days=1)}),
            ("oldest", "najstaršie", {"box": 1, "due_at": now - timedelta(days=9)}),
        ])
    finally:
        db.close()

    words = {item["original_word"] for item in _session(client)}
    assert words == {"new", "recent", "oldest"}          # „later" ešte nie je na rade


def test_session_is_capped_and_takes_the_oldest_due_first(client, db_factory):
    email = "srs-cap@example.com"
    _login(client, email)
    db = db_factory()
    try:
        user_id = _user(db, email).id
        now = utcnow()
        _set(db, user_id, words=[
            (f"word{i}", f"slovo{i}", {"box": 1, "due_at": now - timedelta(days=i + 1)})
            for i in range(SESSION_SIZE + 5)
        ])
    finally:
        db.close()

    words = {item["original_word"] for item in _session(client)}
    assert len(words) == SESSION_SIZE
    assert words == {f"word{i}" for i in range(5, SESSION_SIZE + 5)}


def test_free_account_learns_only_from_the_unlocked_set(client, db_factory):
    """Výber naprieč sadami nesmie obísť zámok free účtu."""
    email = "srs-lock@example.com"
    _login(client, email)
    db = db_factory()
    try:
        user_id = _user(db, email).id
        now = utcnow()
        locked = _set(db, user_id, "Stará", [("old", "staré")], created=now - timedelta(days=9))
        _set(db, user_id, "Nová", [("fresh", "čerstvé")], created=now)
    finally:
        db.close()

    assert [item["original_word"] for item in _session(client)] == ["fresh"]
    assert client.get("/api/v1/learn/session", params={"category_id": locked}).status_code == 403
    assert client.get("/api/dashboard", params={"today": 1}).json()["today"]["new"] == 1


def test_plus_account_learns_across_all_sets(client, db_factory):
    email = "srs-plus@example.com"
    _login(client, email)
    db = db_factory()
    try:
        user = _user(db, email)
        user.is_plus = True
        db.commit()
        now = utcnow()
        _set(db, user.id, "Stará", [("old", "staré")], created=now - timedelta(days=9))
        _set(db, user.id, "Nová", [("fresh", "čerstvé")], created=now)
    finally:
        db.close()

    assert {item["original_word"] for item in _session(client)} == {"old", "fresh"}


def test_foreign_set_is_refused(client, db_factory):
    db = db_factory()
    try:
        stranger = User(email="srs-stranger@example.com", name="X", password="x")
        db.add(stranger)
        db.commit()
        foreign = _set(db, stranger.id, "Cudzia", [("secret", "tajné")])
    finally:
        db.close()

    _login(client, "srs-foreign@example.com")
    assert client.get("/api/v1/learn/session", params={"category_id": foreign}).status_code == 404


def _class_with_set(db, student_id, words):
    teacher = User(email=f"srs-teacher{student_id}@example.com", name="T", password="x")
    db.add(teacher)
    db.commit()
    category_id = _set(db, teacher.id, "Trieda", words)
    school_class = SchoolClass(name="5.A", teacher_id=teacher.id, join_code=f"SRS{student_id}")
    db.add(school_class)
    db.flush()
    db.add(ClassMember(class_id=school_class.id, user_id=student_id, nickname="Žiak"))
    db.add(ClassCategory(class_id=school_class.id, category_id=category_id))
    db.commit()
    return category_id


def test_class_words_are_learned_on_the_students_own_schedule(client, db_factory):
    """Slová patria učiteľovi: pokrok žiaka musí ísť do word_progress."""
    email = "srs-student@example.com"
    _login(client, email)
    db = db_factory()
    try:
        student_id = _user(db, email).id
        category_id = _class_with_set(db, student_id, [("board", "tabuľa")])
    finally:
        db.close()

    items = _session(client)
    assert [item["original_word"] for item in items] == ["board"]
    assert client.get("/api/dashboard", params={"today": 1}).json()["today"]["new"] == 1

    client.post("/api/v1/words/test/submit", json=[{"word_id": items[0]["id"], "is_correct": True}])

    db = db_factory()
    try:
        word = db.query(Word).filter(Word.category_id == category_id).one()
        assert word.box == 0 and word.due_at is None
        progress = db.query(WordProgress).filter(WordProgress.user_id == student_id).one()
        assert progress.box == 1 and progress.due_at > utcnow()
    finally:
        db.close()

    assert _session(client) == []          # dnes už nie je na rade
    today = client.get("/api/dashboard", params={"today": 1}).json()["today"]
    assert today["new"] == 0 and today["due"] == 0


def test_today_summary_counts_due_and_new(client, db_factory):
    email = "srs-today@example.com"
    _login(client, email)
    db = db_factory()
    try:
        user_id = _user(db, email).id
        now = utcnow()
        _set(db, user_id, words=[
            ("a", "1"), ("b", "2"),
            ("c", "3", {"box": 1, "due_at": now - timedelta(hours=1)}),
            ("d", "4", {"box": 3, "due_at": now + timedelta(days=4)}),
        ])
    finally:
        db.close()

    today = client.get("/api/dashboard", params={"today": 1}).json()["today"]
    assert today == {"due": 1, "new": 2, "session_size": SESSION_SIZE}
    # Sady a Štatistiky dávku neplatia.
    assert "today" not in client.get("/api/dashboard").json()


def test_extra_session_ignores_due_dates(client, db_factory):
    email = "srs-extra@example.com"
    _login(client, email)
    db = db_factory()
    try:
        user_id = _user(db, email).id
        now = utcnow()
        category_id = _set(db, user_id, words=[
            ("later", "neskôr", {"box": 2, "due_at": now + timedelta(days=2)}),
        ])
    finally:
        db.close()

    assert _session(client) == []
    assert [i["original_word"] for i in _session(client, extra="true")] == ["later"]
    # Stránka sady sa dá učiť vždy, aj keď v nej nič nie je na rade.
    assert [i["original_word"] for i in _session(client, category_id=category_id)] == ["later"]


def test_query_count_does_not_grow_with_the_session(client, db_factory):
    """Nad vzdialenou databázou stojí každý dotaz ~112 ms."""
    email = "srs-queries@example.com"
    _login(client, email)
    db = db_factory()
    try:
        user_id = _user(db, email).id
        now = utcnow()
        _set(db, user_id, words=[
            (f"word{i}", f"slovo{i}", {"box": i % 4, "due_at": now - timedelta(days=1)})
            for i in range(30)
        ])
        bind = db.get_bind()
    finally:
        db.close()

    statements = []
    def count(_conn, _cursor, statement, *_args):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)
    event.listen(bind, "before_cursor_execute", count)
    try:
        assert len(_session(client)) == SESSION_SIZE
    finally:
        event.remove(bind, "before_cursor_execute", count)
    assert len(statements) <= 6, statements


# ── úlohy ──

@pytest.mark.parametrize("box, can_choose, can_cloze, expected", [
    (0, True, True, {CARD}),
    (1, True, True, {CHOICE}),
    (2, True, True, {CLOZE}),
    (2, True, False, {CHOICE}),
    (3, True, True, {LISTEN, CLOZE}),
    (5, True, False, {LISTEN, CHOICE}),
    (3, False, False, {CARD}),
])
def test_exercise_gets_harder_with_the_box(box, can_choose, can_cloze, expected):
    rng = random.Random(1)
    assert {pick_exercise(box, can_choose, can_cloze, rng) for _ in range(30)} == expected


def test_choice_offers_translations_and_contains_the_answer(client, db_factory):
    email = "srs-choice@example.com"
    _login(client, email)
    db = db_factory()
    try:
        user_id = _user(db, email).id
        now = utcnow()
        _set(db, user_id, words=[
            ("dog", "pes", {"box": 1, "due_at": now - timedelta(days=1)}),
            ("cat", "mačka", {"box": 3, "due_at": now + timedelta(days=9)}),
            ("cow", "krava", {"box": 3, "due_at": now + timedelta(days=9)}),
        ])
    finally:
        db.close()

    item = _session(client)[0]
    assert item["exercise"] == CHOICE
    assert item["answer"] == "pes"
    assert set(item["options"]) == {"pes", "mačka", "krava"}


def test_phrases_get_a_gap_inside_the_phrase(client, db_factory):
    """Sady Miloša sú frázy a dialógy, nie jednotlivé slová."""
    email = "srs-phrase@example.com"
    _login(client, email)
    phrases = [
        "When did you go? – Last September.",
        "Where did you stay? – In a small hotel.",
        "How long were you there? – About two weeks.",
        "Who did you travel with? – With my family.",
    ]
    db = db_factory()
    try:
        user_id = _user(db, email).id
        now = utcnow()
        _set(db, user_id, words=[
            (phrase, f"preklad {i}", {"box": 2, "due_at": now - timedelta(days=1)})
            for i, phrase in enumerate(phrases)
        ])
    finally:
        db.close()

    items = _session(client)
    assert len(items) == len(phrases)
    for item in items:
        assert item["exercise"] == CLOZE
        assert item["answer"] in item["options"]
        assert item["sentence_before"] + item["sentence_hidden"] + item["sentence_after"] == item["original_word"]


def test_single_word_set_falls_back_to_a_card(client, db_factory):
    email = "srs-single@example.com"
    _login(client, email)
    db = db_factory()
    try:
        user_id = _user(db, email).id
        _set(db, user_id, words=[("dog", "pes", {"box": 3, "due_at": utcnow() - timedelta(days=1)})])
    finally:
        db.close()

    assert _session(client)[0]["exercise"] == CARD


# ── stránky ──

def test_learn_page_needs_login(client):
    client.post("/api/v1/logout")
    res = client.get("/ucenie", follow_redirects=False)
    assert res.status_code in (302, 303)
    assert res.headers["location"] == "/login"


def test_learn_page_has_no_tabs(client):
    _login(client, "srs-page@example.com")
    page = client.get("/ucenie").text
    assert "/static/js/page-learn.js" in page
    assert 'class="app-tabs"' not in page


def test_set_page_learns_through_the_new_screen(client, db_factory):
    email = "srs-set@example.com"
    _login(client, email)
    db = db_factory()
    try:
        category_id = _set(db, _user(db, email).id, words=[("dog", "pes")])
    finally:
        db.close()

    page = client.get(f"/category/{category_id}/words").text
    assert f'href="/ucenie?category={category_id}"' in page


def test_learning_answers_cannot_be_lost():
    import io

    script = io.open("app/static/js/page-learn.js", encoding="utf-8").read()
    assert "sendBeacon" in script                     # zavretá karta, späť, prepnutie appky
    assert "answers.slice(pendingFrom)" in script     # nič sa nezapíše dvakrát
    assert "queueTestResults" in script               # výpadok siete
