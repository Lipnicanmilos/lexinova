"""Triedy (Fáza 2 učiteľského kanála) — CRUD, join, pseudonymné účty, login.

Pokrýva: PLUS gate na založenie, formát kódu, regenerate, join e-mailového
usera (kolízia prezývky, idempotencia, vlastná trieda), pseudonymnú registráciu
(join-new), login kódom triedy, reset hesla učiteľom, mazanie triedy vrátane
osirotených pseudonymných účtov, verejný preview.
"""

from app.models.school_class import ClassMember, SchoolClass
from app.models.user import User
from app.routers.classes import JOIN_CODE_ALPHABET, JOIN_CODE_LENGTH


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


def _teacher_with_class(client, db_factory, email, class_name="5.A"):
    """Registrácia učiteľa + PLUS + trieda. Vráti (teacher, class_dict)."""
    teacher = _register(client, email)
    _set_plus(db_factory, email)
    res = client.post("/api/v1/classes", json={"name": class_name})
    assert res.status_code == 200
    return teacher, res.json()


# ── Založenie a správa triedy ──

def test_create_class_requires_plus(client):
    _register(client, "ucitel1@example.com")
    res = client.post("/api/v1/classes", json={"name": "5.A"})
    assert res.status_code == 403


def test_create_class_code_format(client, db_factory):
    _, cls = _teacher_with_class(client, db_factory, "ucitel2@example.com")
    assert len(cls["join_code"]) == JOIN_CODE_LENGTH
    assert all(ch in JOIN_CODE_ALPHABET for ch in cls["join_code"])
    assert cls["join_url"].endswith(f"/c/{cls['join_code']}")


def test_list_rename_class(client, db_factory):
    _, cls = _teacher_with_class(client, db_factory, "ucitel3@example.com")
    res = client.get("/api/v1/classes")
    assert [c["id"] for c in res.json()] == [cls["id"]]

    res = client.put(f"/api/v1/classes/{cls['id']}", json={"name": "6.B"})
    assert res.status_code == 200
    assert res.json()["name"] == "6.B"


def test_foreign_class_404(client, db_factory):
    _, cls = _teacher_with_class(client, db_factory, "ucitel4@example.com")
    _logout(client)
    _register(client, "cudzi4@example.com")
    assert client.put(f"/api/v1/classes/{cls['id']}", json={"name": "X"}).status_code == 404
    assert client.delete(f"/api/v1/classes/{cls['id']}").status_code == 404
    assert client.get(f"/api/v1/classes/{cls['id']}/members").status_code == 404
    assert client.get(f"/api/v1/classes/{cls['id']}/overview").status_code == 403  # PLUS gate skôr


def test_regenerate_code_invalidates_old(client, db_factory):
    _, cls = _teacher_with_class(client, db_factory, "ucitel5@example.com")
    old_code = cls["join_code"]
    res = client.post(f"/api/v1/classes/{cls['id']}/regenerate-code")
    new_code = res.json()["join_code"]
    assert new_code != old_code
    assert client.get(f"/api/v1/classes/preview/{old_code}").status_code == 404
    assert client.get(f"/api/v1/classes/preview/{new_code}").status_code == 200


def test_expired_plus_can_manage_but_not_create(client, db_factory):
    """Frozen-management: bez PLUS sa trieda spravuje, ale nová sa nezaloží."""
    _, cls = _teacher_with_class(client, db_factory, "ucitel6@example.com")
    _set_plus(db_factory, "ucitel6@example.com", False)
    assert client.get("/api/v1/classes").status_code == 200
    assert client.put(f"/api/v1/classes/{cls['id']}", json={"name": "Y"}).status_code == 200
    assert client.post("/api/v1/classes", json={"name": "Nová"}).status_code == 403
    assert client.get(f"/api/v1/classes/{cls['id']}/overview").status_code == 403


# ── Join e-mailového usera ──

def test_email_user_join_and_nickname_collision(client, db_factory):
    _, cls = _teacher_with_class(client, db_factory, "ucitel7@example.com")
    _logout(client)

    _register(client, "ziak7a@example.com")
    res = client.post(
        "/api/v1/classes/join", json={"class_code": cls["join_code"], "nickname": "Miško"}
    )
    assert res.status_code == 200
    assert res.json()["already_member"] is False

    # idempotentné druhé pridanie
    res = client.post(
        "/api/v1/classes/join", json={"class_code": cls["join_code"], "nickname": "Miško"}
    )
    assert res.json()["already_member"] is True

    # kolízia prezývky iným userom
    _logout(client)
    _register(client, "ziak7b@example.com")
    res = client.post(
        "/api/v1/classes/join", json={"class_code": cls["join_code"], "nickname": "Miško"}
    )
    assert res.status_code == 409

    # /mine vidí členstvo
    res = client.post(
        "/api/v1/classes/join", json={"class_code": cls["join_code"], "nickname": "Janko"}
    )
    assert res.status_code == 200
    mine = client.get("/api/v1/classes/mine").json()
    assert [m["class_id"] for m in mine] == [cls["id"]]
    assert mine[0]["nickname"] == "Janko"


def test_teacher_cannot_join_own_class(client, db_factory):
    _, cls = _teacher_with_class(client, db_factory, "ucitel8@example.com")
    res = client.post(
        "/api/v1/classes/join", json={"class_code": cls["join_code"], "nickname": "Ja"}
    )
    assert res.status_code == 400


def test_join_unknown_code_404(client):
    _register(client, "ziak9@example.com")
    res = client.post("/api/v1/classes/join", json={"class_code": "XXXXXX", "nickname": "Miško"})
    assert res.status_code == 404


# ── Pseudonymná registrácia (join-new) a login ──

def test_join_new_creates_pseudonymous_user(client, db_factory):
    _, cls = _teacher_with_class(client, db_factory, "ucitel10@example.com")
    _logout(client)

    res = client.post(
        "/api/v1/classes/join-new",
        json={"class_code": cls["join_code"], "nickname": "Zuzka", "password": "Abcdef12"},
    )
    assert res.status_code == 200

    # session funguje, účet je pseudonymný a bez e-mailu
    me = client.get("/api/user")
    assert me.status_code == 200
    assert me.json()["is_pseudonymous"] is True
    assert me.json()["email"] is None
    assert me.json()["name"] == "Zuzka"

    db = db_factory()
    try:
        user = db.query(User).filter(User.id == me.json()["id"]).first()
        assert user.email is None and user.is_pseudonymous
    finally:
        db.close()


def test_join_new_rejected_when_logged_in(client, db_factory):
    _, cls = _teacher_with_class(client, db_factory, "ucitel11@example.com")
    res = client.post(
        "/api/v1/classes/join-new",
        json={"class_code": cls["join_code"], "nickname": "Zuzka", "password": "Abcdef12"},
    )
    assert res.status_code == 400


def test_join_new_weak_password_and_bad_nickname(client, db_factory):
    _, cls = _teacher_with_class(client, db_factory, "ucitel12@example.com")
    _logout(client)
    res = client.post(
        "/api/v1/classes/join-new",
        json={"class_code": cls["join_code"], "nickname": "Zuzka", "password": "slabe"},
    )
    assert res.status_code == 400
    res = client.post(
        "/api/v1/classes/join-new",
        json={"class_code": cls["join_code"], "nickname": "A", "password": "Abcdef12"},
    )
    assert res.status_code == 400


def test_class_login_flow(client, db_factory):
    _, cls = _teacher_with_class(client, db_factory, "ucitel13@example.com")
    _logout(client)
    client.post(
        "/api/v1/classes/join-new",
        json={"class_code": cls["join_code"], "nickname": "Peťo", "password": "Abcdef12"},
    )
    _logout(client)

    # zlé heslo aj neznáma prezývka → rovnaká hláška (žiadna enumerácia)
    bad_pw = client.post(
        "/api/v1/classes/login",
        json={"class_code": cls["join_code"], "nickname": "Peťo", "password": "Zle12345"},
    )
    bad_nick = client.post(
        "/api/v1/classes/login",
        json={"class_code": cls["join_code"], "nickname": "Nikto", "password": "Abcdef12"},
    )
    assert bad_pw.status_code == bad_nick.status_code == 400
    assert bad_pw.json()["detail"] == bad_nick.json()["detail"]

    # správny login (kód aj malými písmenami)
    res = client.post(
        "/api/v1/classes/login",
        json={"class_code": cls["join_code"].lower(), "nickname": "Peťo", "password": "Abcdef12"},
    )
    assert res.status_code == 200
    assert client.get("/api/user").json()["is_pseudonymous"] is True


# ── Reset hesla učiteľom ──

def test_teacher_resets_pseudonymous_password_only(client, db_factory):
    teacher, cls = _teacher_with_class(client, db_factory, "ucitel14@example.com")
    _logout(client)
    client.post(
        "/api/v1/classes/join-new",
        json={"class_code": cls["join_code"], "nickname": "Ema", "password": "Abcdef12"},
    )
    _logout(client)
    _register(client, "ziak14@example.com")
    client.post("/api/v1/classes/join", json={"class_code": cls["join_code"], "nickname": "Filip"})
    _logout(client)

    client.post("/api/v1/login", json={"email": "ucitel14@example.com", "password": "Abcdef12"})
    members = client.get(f"/api/v1/classes/{cls['id']}/members").json()
    by_nick = {m["nickname"]: m for m in members}
    assert by_nick["Ema"]["is_pseudonymous"] is True
    assert by_nick["Filip"]["is_pseudonymous"] is False

    # e-mailový účet resetnúť NEmožno
    res = client.post(
        f"/api/v1/classes/{cls['id']}/members/{by_nick['Filip']['id']}/reset-password",
        json={"new_password": "Nove1234"},
    )
    assert res.status_code == 403

    # pseudonymný áno — a nové heslo funguje
    res = client.post(
        f"/api/v1/classes/{cls['id']}/members/{by_nick['Ema']['id']}/reset-password",
        json={"new_password": "Nove1234"},
    )
    assert res.status_code == 200
    _logout(client)
    res = client.post(
        "/api/v1/classes/login",
        json={"class_code": cls["join_code"], "nickname": "Ema", "password": "Nove1234"},
    )
    assert res.status_code == 200


# ── Odstránenie člena / odchod / mazanie triedy ──

def test_remove_member_and_leave(client, db_factory):
    _, cls = _teacher_with_class(client, db_factory, "ucitel15@example.com")
    _logout(client)
    _register(client, "ziak15@example.com")
    client.post("/api/v1/classes/join", json={"class_code": cls["join_code"], "nickname": "Kubo"})

    # žiak odíde sám
    assert client.post(f"/api/v1/classes/{cls['id']}/leave").status_code == 200
    assert client.get("/api/v1/classes/mine").json() == []
    assert client.post(f"/api/v1/classes/{cls['id']}/leave").status_code == 404

    # znovu sa pridá a odstráni ho učiteľ
    client.post("/api/v1/classes/join", json={"class_code": cls["join_code"], "nickname": "Kubo"})
    _logout(client)
    client.post("/api/v1/login", json={"email": "ucitel15@example.com", "password": "Abcdef12"})
    members = client.get(f"/api/v1/classes/{cls['id']}/members").json()
    res = client.delete(f"/api/v1/classes/{cls['id']}/members/{members[0]['id']}")
    assert res.status_code == 200
    assert client.get(f"/api/v1/classes/{cls['id']}/members").json() == []


def test_delete_class_removes_orphan_pseudonymous_accounts(client, db_factory):
    _, cls = _teacher_with_class(client, db_factory, "ucitel16@example.com")
    _logout(client)
    client.post(
        "/api/v1/classes/join-new",
        json={"class_code": cls["join_code"], "nickname": "Sirota", "password": "Abcdef12"},
    )
    pseudo_id = client.get("/api/user").json()["id"]
    _logout(client)
    _register(client, "ziak16@example.com")
    email_user_id = client.get("/api/user").json()["id"]
    client.post("/api/v1/classes/join", json={"class_code": cls["join_code"], "nickname": "Ostane"})
    _logout(client)

    client.post("/api/v1/login", json={"email": "ucitel16@example.com", "password": "Abcdef12"})
    res = client.delete(f"/api/v1/classes/{cls['id']}")
    assert res.status_code == 200
    assert res.json()["deleted_student_accounts"] == 1

    db = db_factory()
    try:
        assert db.query(User).filter(User.id == pseudo_id).first() is None
        assert db.query(User).filter(User.id == email_user_id).first() is not None
        assert db.query(SchoolClass).filter(SchoolClass.id == cls["id"]).first() is None
        assert db.query(ClassMember).filter(ClassMember.class_id == cls["id"]).count() == 0
    finally:
        db.close()


# ── Verejný preview ──

def test_class_preview_public(client, db_factory):
    _, cls = _teacher_with_class(client, db_factory, "ucitel17@example.com", class_name="7.C")
    _logout(client)
    res = client.get(f"/api/v1/classes/preview/{cls['join_code'].lower()}")
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "7.C"
    assert body["member_count"] == 0
    assert "members" not in body  # žiadny zoznam žiakov na verejnom endpointe
    assert client.get("/api/v1/classes/preview/NEXIST1").status_code == 404
