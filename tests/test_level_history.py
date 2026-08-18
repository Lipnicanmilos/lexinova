"""História zmien úrovne slovíčka (word_level_events).

Zapisuje sa LEN pri skutočnej zmene úrovne — inak by tabuľka rástla s každým
zopakovaním karty. Z nej sa počíta „naučené za posledný týždeň".
"""

from app.models.word import KnowledgeLevel, Word
from app.models.word_level_event import WordLevelEvent


def _register(client, email):
    res = client.post("/api/v1/register", json={"email": email, "password": "Abcdef12"})
    assert res.status_code == 200
    return res.json()["user"]


def _create_category(client, name, user_id):
    res = client.post(
        "/api/v1/categories", json={"name": name, "description": "popis", "user_id": user_id}
    )
    assert res.status_code == 200
    return res.json()


def _add_word(client, category_id, original="dog"):
    res = client.post(
        "/api/v1/words",
        json={"original_word": original, "translation": "pes", "category_id": category_id},
    )
    assert res.status_code == 200
    return res.json()["id"]


def _events(db_factory, word_id):
    db = db_factory()
    try:
        return (
            db.query(WordLevelEvent)
            .filter(WordLevelEvent.word_id == word_id)
            .order_by(WordLevelEvent.id)
            .all()
        )
    finally:
        db.close()


def test_test_submit_records_only_real_level_changes(client, db_factory):
    user = _register(client, "hist1@example.com")
    category = _create_category(client, "Zvieratá", user["id"])
    word_id = _add_word(client, category["id"])

    # dont_know → know (zmena, zapíše sa)
    client.post("/api/v1/words/test/submit", json=[{"word_id": word_id, "is_correct": True}])
    # know → know (bez zmeny, nezapisuje sa)
    client.post("/api/v1/words/test/submit", json=[{"word_id": word_id, "is_correct": True}])

    events = _events(db_factory, word_id)
    assert [(e.previous_level, e.level) for e in events] == [("dont_know", "know")]

    # know → dont_know (zmena späť, zapíše sa)
    client.post("/api/v1/words/test/submit", json=[{"word_id": word_id, "is_correct": False}])
    events = _events(db_factory, word_id)
    assert [(e.previous_level, e.level) for e in events] == [
        ("dont_know", "know"),
        ("know", "dont_know"),
    ]


def test_manual_level_change_is_recorded(client, db_factory):
    user = _register(client, "hist2@example.com")
    category = _create_category(client, "Cestovanie", user["id"])
    word_id = _add_word(client, category["id"], "train")

    res = client.put(
        f"/api/v1/words/{word_id}/knowledge-level",
        json={"knowledge_level": KnowledgeLevel.LEARNING.value},
    )
    assert res.status_code == 200
    # rovnaká úroveň ešte raz — nový riadok nevznikne
    client.put(
        f"/api/v1/words/{word_id}/knowledge-level",
        json={"knowledge_level": KnowledgeLevel.LEARNING.value},
    )

    events = _events(db_factory, word_id)
    assert [(e.previous_level, e.level) for e in events] == [("dont_know", "learning")]


def test_stats_expose_learned_last_week(client, db_factory):
    user = _register(client, "hist3@example.com")
    category = _create_category(client, "Jedlo", user["id"])
    first = _add_word(client, category["id"], "bread")
    second = _add_word(client, category["id"], "milk")

    client.post("/api/v1/words/test/submit", json=[
        {"word_id": first, "is_correct": True},
        {"word_id": second, "is_correct": False},
    ])

    data = client.get("/api/user/stats").json()
    assert data["learned_7d"] == 1     # len "bread" sa dostal na "Viem"
    assert data["learned_30d"] == 1
    assert data["tests_total"] == 1    # jeden odoslaný test, nie počet kariet


def test_stats_expose_weak_categories(client, db_factory):
    user = _register(client, "hist4@example.com")
    category = _create_category(client, "Slabá", user["id"])
    word_id = _add_word(client, category["id"], "difficult")

    db = db_factory()
    try:
        word = db.query(Word).filter(Word.id == word_id).first()
        word.times_tested = 10
        word.times_correct = 2
        db.commit()
    finally:
        db.close()

    data = client.get("/api/user/stats").json()
    weak = data["weak_categories"]
    assert len(weak) == 1
    assert weak[0]["name"] == "Slabá"
    assert weak[0]["accuracy"] == 20
