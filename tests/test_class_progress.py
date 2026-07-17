"""Sady triedy — live prístup žiakov + overlay pokrok (word_progress).

Pokrýva: priradenie sady triede, zobrazenie v GET /categories (from_class,
mimo limitu kategórií), test/start a get_words nad triednou sadou, zápis
pokroku do word_progress (učiteľove Word stĺpce nedotknuté), regresiu vlastnej
cesty, prehľad triedy a live propagáciu úprav učiteľa.
"""

from app.models.user import User
from app.models.word import Word
from app.models.word_progress import WordProgress
from app.services.limits import CATEGORY_LIMIT_FREE


def _register(client, email):
    res = client.post("/api/v1/register", json={"email": email, "password": "Abcdef12"})
    assert res.status_code == 200
    return res.json()["user"]


def _logout(client):
    client.post("/api/v1/logout")


def _set_plus(db_factory, email, value=True):
    db = db_factory()
    try:
        user = db.query(User).filter(User.email == email).first()
        user.is_plus = value
        db.commit()
    finally:
        db.close()


def _create_category(client, name, user_id):
    res = client.post(
        "/api/v1/categories", json={"name": name, "description": "popis", "user_id": user_id}
    )
    assert res.status_code == 200
    return res.json()


def _seed_words(db_factory, user_id, category_id, n):
    db = db_factory()
    try:
        for i in range(n):
            db.add(Word(original_word=f"word{i}", translation=f"slovo{i}",
                        category_id=category_id, user_id=user_id,
                        language_from="en", language_to="sk"))
        db.commit()
    finally:
        db.close()


def _class_with_set(client, db_factory, teacher_email, n_words=3):
    """Učiteľ (PLUS) + trieda + kategória so slovami priradená triede.

    Vráti (teacher, class_dict, category_dict). Klient ostáva prihlásený ako učiteľ.
    """
    teacher = _register(client, teacher_email)
    _set_plus(db_factory, teacher_email)
    cls = client.post("/api/v1/classes", json={"name": "5.A"}).json()
    cat = _create_category(client, "Triedna sada", teacher["id"])
    _seed_words(db_factory, teacher["id"], cat["id"], n_words)
    res = client.post(f"/api/v1/classes/{cls['id']}/categories", json={"category_id": cat["id"]})
    assert res.status_code == 200
    return teacher, cls, cat


def _join_as_pseudo(client, cls, nickname="Žiak"):
    res = client.post(
        "/api/v1/classes/join-new",
        json={"class_code": cls["join_code"], "nickname": nickname, "password": "Abcdef12"},
    )
    assert res.status_code == 200
    return res.json()


# ── Priradenie sady ──

def test_assign_requires_owned_category(client, db_factory):
    _register(client, "ineho@example.com")
    foreign_cat = _create_category(client, "Cudzia", client.get("/api/user").json()["id"])
    _logout(client)

    teacher = _register(client, "ucitelA@example.com")
    _set_plus(db_factory, "ucitelA@example.com")
    cls = client.post("/api/v1/classes", json={"name": "5.A"}).json()
    res = client.post(
        f"/api/v1/classes/{cls['id']}/categories", json={"category_id": foreign_cat["id"]}
    )
    assert res.status_code == 404

    own = _create_category(client, "Moja", teacher["id"])
    assert client.post(
        f"/api/v1/classes/{cls['id']}/categories", json={"category_id": own["id"]}
    ).status_code == 200
    # unassign
    assert client.delete(
        f"/api/v1/classes/{cls['id']}/categories/{own['id']}"
    ).status_code == 200
    assert client.delete(
        f"/api/v1/classes/{cls['id']}/categories/{own['id']}"
    ).status_code == 404


# ── Zobrazenie v zozname kategórií ──

def test_class_category_in_list_with_flag(client, db_factory):
    _, cls, cat = _class_with_set(client, db_factory, "ucitelB@example.com")
    _logout(client)
    _join_as_pseudo(client, cls)

    cats = client.get("/api/v1/categories").json()
    assert len(cats) == 1
    entry = cats[0]
    assert entry["id"] == cat["id"]
    assert entry["from_class"] is True
    assert entry["class_name"] == "5.A"
    assert entry["share_code"] is None
    assert entry["total_words"] == 3
    assert entry["level_counts"]["dont_know"] == 3  # bez progress = netestované


def test_class_category_not_counted_in_limit(client, db_factory):
    _, cls, _cat = _class_with_set(client, db_factory, "ucitelC@example.com")
    _logout(client)
    ziak = _register(client, "ziakC@example.com")
    client.post("/api/v1/classes/join", json={"class_code": cls["join_code"], "nickname": "Miša"})

    # žiak naplní vlastný limit kategórií — triedna sada sa nepočíta
    for i in range(CATEGORY_LIMIT_FREE):
        _create_category(client, f"Vlastná {i}", ziak["id"])
    res = client.post(
        "/api/v1/categories",
        json={"name": "Nad limit", "description": "", "user_id": ziak["id"]},
    )
    assert res.status_code == 400  # vlastný limit platí

    cats = client.get("/api/v1/categories").json()
    assert len(cats) == CATEGORY_LIMIT_FREE + 1  # 5 vlastných + triedna
    assert sum(1 for c in cats if c["from_class"]) == 1


# ── Test a slová nad triednou sadou ──

def test_start_test_and_get_words_on_class_set(client, db_factory):
    _, cls, cat = _class_with_set(client, db_factory, "ucitelD@example.com")
    _logout(client)
    _join_as_pseudo(client, cls)

    res = client.post("/api/v1/words/test/start", json={"category_id": cat["id"], "knowledge_levels": ["dont_know", "learning", "know"], "limit": 10})
    assert res.status_code == 200
    words = res.json()
    assert len(words) == 3
    assert all(w["knowledge_level"] == "dont_know" and w["times_tested"] == 0 for w in words)

    res = client.get(f"/api/v1/words?category_id={cat['id']}")
    assert res.status_code == 200
    assert res.json()["total"] == 3


def test_non_member_cannot_start_class_test(client, db_factory):
    _, _cls, cat = _class_with_set(client, db_factory, "ucitelE@example.com")
    _logout(client)
    _register(client, "nikto@example.com")
    res = client.post("/api/v1/words/test/start", json={"category_id": cat["id"], "knowledge_levels": ["dont_know", "learning", "know"], "limit": 10})
    assert res.status_code == 404
    # get_words vráti prázdno (pôvodné správanie pre cudziu kategóriu)
    assert client.get(f"/api/v1/words?category_id={cat['id']}").json()["total"] == 0


def test_submit_writes_word_progress_not_teacher_words(client, db_factory):
    _, cls, cat = _class_with_set(client, db_factory, "ucitelF@example.com")
    _logout(client)
    _join_as_pseudo(client, cls)
    ziak_id = client.get("/api/user").json()["id"]

    words = client.post(
        "/api/v1/words/test/start", json={"category_id": cat["id"], "knowledge_levels": ["dont_know", "learning", "know"], "limit": 10}
    ).json()
    results = [
        {"word_id": words[0]["id"], "is_correct": True},
        {"word_id": words[1]["id"], "is_correct": False},
    ]
    res = client.post("/api/v1/words/test/submit", json=results)
    assert res.status_code == 200
    updated = {w["id"]: w for w in res.json()["updated_words"]}
    assert updated[words[0]["id"]]["knowledge_level"] == "know"
    assert updated[words[1]["id"]]["knowledge_level"] == "dont_know"

    db = db_factory()
    try:
        # učiteľove Word riadky NEDOTKNUTÉ
        for w in db.query(Word).filter(Word.category_id == cat["id"]).all():
            assert w.times_tested == 0 and w.knowledge_level.value == "dont_know"
        # pokrok žiaka vo word_progress
        rows = db.query(WordProgress).filter(WordProgress.user_id == ziak_id).all()
        assert len(rows) == 2
        by_word = {r.word_id: r for r in rows}
        assert by_word[words[0]["id"]].times_correct == 1
        assert by_word[words[1]["id"]].times_correct == 0
    finally:
        db.close()

    # druhé kolo — upsert (nie duplicitný riadok)
    client.post("/api/v1/words/test/submit", json=[{"word_id": words[0]["id"], "is_correct": True}])
    db = db_factory()
    try:
        rows = db.query(WordProgress).filter(
            WordProgress.user_id == ziak_id, WordProgress.word_id == words[0]["id"]
        ).all()
        assert len(rows) == 1
        assert rows[0].times_tested == 2
    finally:
        db.close()

    # overlay sa premietne do zoznamu kategórií žiaka
    entry = client.get("/api/v1/categories").json()[0]
    assert entry["level_counts"]["know"] == 1
    assert entry["level_counts"]["dont_know"] == 2


def test_own_words_regression(client, db_factory):
    """Vlastná cesta (Word stĺpce) musí fungovať ako doteraz."""
    user = _register(client, "vlastnik@example.com")
    cat = _create_category(client, "Moje", user["id"])
    _seed_words(db_factory, user["id"], cat["id"], 2)

    words = client.post(
        "/api/v1/words/test/start", json={"category_id": cat["id"], "knowledge_levels": ["dont_know", "learning", "know"], "limit": 10}
    ).json()
    res = client.post(
        "/api/v1/words/test/submit", json=[{"word_id": words[0]["id"], "is_correct": True}]
    )
    assert res.status_code == 200

    db = db_factory()
    try:
        word = db.query(Word).filter(Word.id == words[0]["id"]).first()
        assert word.times_tested == 1 and word.times_correct == 1
        assert word.knowledge_level.value == "know"
        assert db.query(WordProgress).count() >= 0  # žiadny overlay riadok pre vlastné slovo
        assert (
            db.query(WordProgress)
            .filter(WordProgress.user_id == user["id"], WordProgress.word_id == word.id)
            .first()
            is None
        )
    finally:
        db.close()


def test_foreign_word_without_class_ignored(client, db_factory):
    """Cudzie slovo mimo triednych sád sa pri submite ignoruje (ako doteraz)."""
    owner = _register(client, "ownerG@example.com")
    cat = _create_category(client, "Cudzia", owner["id"])
    _seed_words(db_factory, owner["id"], cat["id"], 1)
    db = db_factory()
    try:
        word_id = db.query(Word).filter(Word.category_id == cat["id"]).first().id
    finally:
        db.close()
    _logout(client)
    _register(client, "utocnik@example.com")
    res = client.post("/api/v1/words/test/submit", json=[{"word_id": word_id, "is_correct": True}])
    assert res.status_code == 200
    assert res.json()["updated_words"] == []


# ── Live odkaz ──

def test_teacher_edit_visible_to_student(client, db_factory):
    _, cls, cat = _class_with_set(client, db_factory, "ucitelH@example.com")
    db = db_factory()
    try:
        word = db.query(Word).filter(Word.category_id == cat["id"]).first()
        word_id = word.id
    finally:
        db.close()

    # učiteľ opraví preklep
    res = client.put(f"/api/v1/words/{word_id}", json={"original_word": "opravene"})
    assert res.status_code == 200
    _logout(client)

    _join_as_pseudo(client, cls)
    words = client.get(f"/api/v1/words?category_id={cat['id']}").json()["words"]
    assert any(w["original_word"] == "opravene" for w in words)
    # a slová triedy žiak nesmie meniť
    assert client.put(
        f"/api/v1/words/{word_id}", json={"original_word": "hack"}
    ).status_code == 403


# ── Prehľad triedy ──

def test_class_overview(client, db_factory):
    _, cls, cat = _class_with_set(client, db_factory, "ucitelI@example.com")
    _logout(client)
    _join_as_pseudo(client, cls, nickname="Ela")
    words = client.post(
        "/api/v1/words/test/start", json={"category_id": cat["id"], "knowledge_levels": ["dont_know", "learning", "know"], "limit": 10}
    ).json()
    client.post(
        "/api/v1/words/test/submit",
        json=[
            {"word_id": words[0]["id"], "is_correct": True},
            {"word_id": words[1]["id"], "is_correct": True},
            {"word_id": words[2]["id"], "is_correct": False},
        ],
    )
    _logout(client)

    client.post("/api/v1/login", json={"email": "ucitelI@example.com", "password": "Abcdef12"})
    res = client.get(f"/api/v1/classes/{cls['id']}/overview")
    assert res.status_code == 200
    body = res.json()
    assert body["class_name"] == "5.A"
    assert [c["id"] for c in body["categories"]] == [cat["id"]]
    assert body["categories"][0]["total_words"] == 3

    assert len(body["members"]) == 1
    member = body["members"][0]
    assert member["nickname"] == "Ela"
    assert member["tests_taken"] == 1
    assert member["success_rate"] == 66.7
    assert member["last_activity"] is not None
    mastery = member["mastery"][str(cat["id"])]
    assert mastery["know"] == 2
    assert mastery["dont_know"] == 1
