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
