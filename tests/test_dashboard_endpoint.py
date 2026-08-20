"""Nástenka jedným requestom namiesto troch.

Merania na produkcii 2026-08-19: tri súbežné requesty trvali 2220 ms každý,
kým samostatný 1076 ms — inštancia súbežnosť neutiahne. K tomu má každý request
vlastnú réžiu (~345 ms nameraných na triviálnom `/api/user`). `/api/dashboard`
vráti to isté naraz.
"""
from app.models.category import Category
from app.models.word import KnowledgeLevel, Word


def _register(client, email):
    res = client.post("/api/v1/register", json={"email": email, "password": "Abcdef12"})
    assert res.status_code == 200


def test_dashboard_returns_user_stats_and_categories(client):
    _register(client, "dash1@example.com")
    cat = client.post("/api/v1/categories",
                      json={"name": "Sada", "description": "popis", "user_id": 1})
    assert cat.status_code == 200

    res = client.get("/api/dashboard")
    assert res.status_code == 200
    body = res.json()

    assert set(body) == {"user", "stats", "categories"}
    assert body["user"]["email"] == "dash1@example.com"
    assert body["stats"]["total_categories"] == 1
    assert [c["name"] for c in body["categories"]] == ["Sada"]


def test_dashboard_matches_the_three_original_endpoints(client, db_factory):
    """Jeden request musí vrátiť presne to, čo tri pôvodné — inak by sa rozišli."""
    _register(client, "dash2@example.com")
    cat = client.post("/api/v1/categories",
                      json={"name": "Nemčina", "description": None, "user_id": 1}).json()

    db = db_factory()
    try:
        from app.models.user import User
        user = db.query(User).filter(User.email == "dash2@example.com").one()
        db.add(Word(original_word="Haus", translation="dom", category_id=cat["id"],
                    user_id=user.id, knowledge_level=KnowledgeLevel.KNOW,
                    times_tested=2, times_correct=2))
        db.commit()
    finally:
        db.close()

    combined = client.get("/api/dashboard").json()
    assert combined["user"] == client.get("/api/user").json()
    assert combined["stats"] == client.get("/api/user/stats").json()
    assert combined["categories"] == client.get("/api/v1/categories").json()


def test_dashboard_requires_login(client):
    client.post("/api/v1/logout")
    assert client.get("/api/dashboard").status_code in (401, 403)


def test_dashboard_page_loads_it_in_one_request():
    """Skript nástenky musí volať zlúčený endpoint, inak je zmena zbytočná."""
    import io

    script = io.open('app/static/js/page-dashboard.js', encoding='utf-8').read()
    init = script[script.index("addEventListener('pageshow'"):][:600]

    assert "loadDashboard()" in init
    for old in ("/api/user'", "/api/user/stats'", "/api/v1/categories'"):
        assert old not in init, f"init stále volá {old}"
