"""Opakovanie (auto-play) sa ráta do aktivity, ale nie do úspešnosti.

Prehrávanie v Opakovaní doteraz neposielalo nič — používateľ si prešiel sto
slovíčok a v štatistikách sa nestalo nič. Zapisuje sa ako `kind='review'`;
keďže sa pri ňom neodpovedá, `correct` je vždy 0 a do priemeru úspešnosti
tieto riadky vstupovať nesmú.
"""
from datetime import date, datetime, timedelta

from app.models.test_session import TestSession as SessionModel
from app.services.stats_service import get_history_stats

TODAY = date(2026, 6, 30)


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


def test_opakovanie_sa_zapise(client, db_factory):
    user = _register(client, "rev1@example.com")
    category = _create_category(client, "Slovesá", user["id"])

    res = client.post(
        "/api/v1/words/review/complete",
        json={"category_id": category["id"], "words_reviewed": 12},
    )
    assert res.status_code == 200

    db = db_factory()
    try:
        row = (
            db.query(SessionModel)
            .filter(SessionModel.user_id == user["id"])
            .order_by(SessionModel.id.desc())
            .first()
        )
        assert row.kind == "review"
        assert row.total == 12
        assert row.correct == 0
        assert row.category_id == category["id"]
    finally:
        db.close()


def test_cudzia_kategoria_sa_neuklada(client):
    """ID cudzej kategórie by inak viedlo na cudziu kategóriu v štatistikách."""
    owner = _register(client, "rev2@example.com")
    foreign = _create_category(client, "Cudzia", owner["id"])
    client.post("/api/v1/logout")

    _register(client, "rev3@example.com")
    res = client.post(
        "/api/v1/words/review/complete",
        json={"category_id": foreign["id"], "words_reviewed": 5},
    )
    assert res.status_code == 200
    assert client.get("/api/user/stats").json()["reviews_7d"] == 1


def test_opakovanie_vyzaduje_prihlasenie(client):
    client.post("/api/v1/logout")
    res = client.post("/api/v1/words/review/complete", json={"words_reviewed": 3})
    assert res.status_code in (401, 403)


def test_opakovanie_drzi_seriu_ale_neriedi_uspesnost(db_factory):
    db = db_factory()
    user_id = 987657
    try:
        # Včera test 8/10 = 80 %, dnes len opakovanie 30 kariet bez odpovedí.
        db.add(SessionModel(
            user_id=user_id, kind="test", total=10, correct=8,
            created_at=datetime(2026, 6, 29, 10, 0),
        ))
        db.add(SessionModel(
            user_id=user_id, kind="review", total=30, correct=0,
            created_at=datetime(2026, 6, 30, 18, 0),
        ))
        db.commit()

        h = get_history_stats(db, user_id, today=TODAY, days=14)
        assert h["streak_days"] == 2          # opakovanie drží sériu
        assert h["accuracy_7d"] == 80         # ale neriedi úspešnosť
        assert h["tests_total"] == 1          # počet testov ostáva jeden
        assert h["reviews_7d"] == 1

        dnes = h["activity"][-1]
        assert dnes["reviews"] == 1
        assert dnes["tests"] == 0
        assert dnes["accuracy"] is None       # deň bez testu nemá úspešnosť
    finally:
        db.query(SessionModel).filter(SessionModel.user_id == user_id).delete()
        db.commit()
        db.close()
