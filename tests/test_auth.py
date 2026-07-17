"""Registrácia (validácia emailu + sily hesla) a prihlásenie."""


def test_register_valid(client):
    r = client.post("/api/v1/register", json={"email": "valid@example.com", "password": "Abcdef12"})
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "valid@example.com"


def test_register_weak_password_rejected(client):
    # chýba veľké písmeno aj číslica
    r = client.post("/api/v1/register", json={"email": "weak@example.com", "password": "alllower"})
    assert r.status_code == 422


def test_register_short_password_rejected(client):
    r = client.post("/api/v1/register", json={"email": "short@example.com", "password": "Ab1"})
    assert r.status_code == 422


def test_register_invalid_email_rejected(client):
    r = client.post("/api/v1/register", json={"email": "not-an-email", "password": "Abcdef12"})
    assert r.status_code == 422


def test_register_duplicate_rejected(client):
    payload = {"email": "dup@example.com", "password": "Abcdef12"}
    assert client.post("/api/v1/register", json=payload).status_code == 200
    assert client.post("/api/v1/register", json=payload).status_code == 400


def test_login_success(client):
    client.post("/api/v1/register", json={"email": "login@example.com", "password": "Abcdef12"})
    r = client.post("/api/v1/login", json={"email": "login@example.com", "password": "Abcdef12"})
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "login@example.com"


def test_login_wrong_password(client):
    client.post("/api/v1/register", json={"email": "wrongpw@example.com", "password": "Abcdef12"})
    r = client.post("/api/v1/login", json={"email": "wrongpw@example.com", "password": "WrongPass9"})
    assert r.status_code == 400


def test_login_unknown_user(client):
    r = client.post("/api/v1/login", json={"email": "ghost@example.com", "password": "Abcdef12"})
    assert r.status_code == 400


def test_login_no_user_enumeration(client):
    """Zlý e-mail aj zlé heslo musia vrátiť identickú hlášku (žiadna enumerácia účtov)."""
    client.post("/api/v1/register", json={"email": "enum@example.com", "password": "Abcdef12"})
    wrong_password = client.post(
        "/api/v1/login", json={"email": "enum@example.com", "password": "WrongPass9"}
    )
    unknown_email = client.post(
        "/api/v1/login", json={"email": "neexistuje@example.com", "password": "WrongPass9"}
    )
    assert wrong_password.status_code == unknown_email.status_code == 400
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"]


def test_logout_requires_post(client):
    client.post("/api/v1/register", json={"email": "lgout@example.com", "password": "Abcdef12"})
    # GET nesmie odhlásiť (CSRF cez obyčajný link)
    assert client.get("/api/v1/logout").status_code == 405
    assert client.post("/api/v1/logout").status_code == 200
    # session je zrušená
    assert client.get("/api/user").status_code == 401


def test_change_password_flow(client):
    client.post("/api/v1/register", json={"email": "chpw@example.com", "password": "Abcdef12"})

    # nesprávne súčasné heslo
    r = client.post("/api/user/change-password", json={"current_password": "Wrong1AA", "new_password": "Newpass12"})
    assert r.status_code == 400
    # slabé nové heslo
    r = client.post("/api/user/change-password", json={"current_password": "Abcdef12", "new_password": "weak"})
    assert r.status_code == 400
    # úspešná zmena
    r = client.post("/api/user/change-password", json={"current_password": "Abcdef12", "new_password": "Newpass12"})
    assert r.status_code == 200

    # staré heslo už neplatí, nové áno
    client.post("/api/v1/logout")
    assert client.post("/api/v1/login", json={"email": "chpw@example.com", "password": "Abcdef12"}).status_code == 400
    assert client.post("/api/v1/login", json={"email": "chpw@example.com", "password": "Newpass12"}).status_code == 200


def test_change_password_requires_auth(client):
    # bez prihlásenia nesmie prejsť
    r = client.post("/api/user/change-password", json={"current_password": "Abcdef12", "new_password": "Newpass12"})
    assert r.status_code in (401, 403)


def test_forgot_password_null_email_no_token(client, db_factory):
    """{"email": null} nesmie matchnúť pseudonymné účty (email IS NULL) ani nastaviť token."""
    from app.models.user import User
    from app.services.auth_service import hash_password

    db = db_factory()
    try:
        pseudo = User(email=None, name="ziak7", password=hash_password("Abcdef12"), is_pseudonymous=True)
        db.add(pseudo)
        db.commit()
        pseudo_id = pseudo.id
    finally:
        db.close()

    r = client.post("/api/v1/forgot-password", json={"email": None})
    assert r.status_code == 200  # generická hláška, žiadny únik

    db = db_factory()
    try:
        assert db.get(User, pseudo_id).reset_token is None
    finally:
        db.close()


def test_forgot_password_non_string_email(client):
    r = client.post("/api/v1/forgot-password", json={"email": {"$ne": ""}})
    assert r.status_code == 200
