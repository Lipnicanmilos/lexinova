"""Osemsmerovka — routa a vstup z kategórie.

Mriežka sa skladá v prehliadači z už načítaných slovíčok, takže server tu
nerobí nič viac než autorizáciu a vykreslenie šablóny.
"""


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


def test_hra_vyzaduje_prihlasenie(client):
    client.post("/api/v1/logout")
    res = client.get("/hra", follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/login"


def test_hra_sa_nacita_pre_kategoriu(client):
    user = _register(client, "hra1@example.com")
    category = _create_category(client, "Cestovanie", user["id"])

    html = client.get(f"/hra?category={category['id']}").text
    assert "Osemsmerovka" in html
    assert category["name"] in html


def test_cudzia_kategoria_presmeruje(client):
    owner = _register(client, "hra2@example.com")
    foreign = _create_category(client, "Cudzia", owner["id"])
    client.post("/api/v1/logout")

    _register(client, "hra3@example.com")
    res = client.get(f"/hra?category={foreign['id']}", follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/dashboard"


def test_kategoria_ponuka_hru(client):
    """Bez vstupu zo stránky kategórie by hru nikto nenašiel."""
    user = _register(client, "hra4@example.com")
    category = _create_category(client, "Jedlo", user["id"])

    html = client.get(f"/category/{category['id']}/words").text
    assert f'href="/hra?category={category["id"]}"' in html
