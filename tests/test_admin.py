"""Admin endpointy — ochrana prístupu + logika grant PLUS / MRR (Fáza 6)."""
from datetime import timedelta

from app.routers.admin import _extended_expiry, _mrr
from app.services.billing_service import PRICE_MONTHLY_EUR, PRICE_ANNUAL_EUR
from app.utils import utcnow


def test_admin_logs_requires_auth(client):
    # Neprihlásený používateľ nesmie čítať logy.
    r = client.get("/api/admin/logs")
    assert r.status_code in (401, 403)


def test_admin_users_requires_auth(client):
    r = client.get("/api/admin/users")
    assert r.status_code in (401, 403)


def test_admin_grant_plus_requires_auth(client):
    r = client.post("/api/admin/users/1/grant-plus", json={"days": 30})
    assert r.status_code in (401, 403)


def test_admin_revoke_plus_requires_auth(client):
    r = client.post("/api/admin/users/1/revoke-plus")
    assert r.status_code in (401, 403)


def test_admin_payments_requires_auth(client):
    r = client.get("/api/admin/payments")
    assert r.status_code in (401, 403)


def test_extended_expiry_from_now_when_expired():
    now = utcnow()
    # Žiadna alebo prošlá expirácia → počíta sa od teraz.
    assert _extended_expiry(None, 30, now) == now + timedelta(days=30)
    past = now - timedelta(days=5)
    assert _extended_expiry(past, 30, now) == now + timedelta(days=30)


def test_extended_expiry_stacks_on_active():
    now = utcnow()
    future = now + timedelta(days=10)
    # Ešte platné PLUS → +30 dní sa pripočíta k zostatku.
    assert _extended_expiry(future, 30, now) == future + timedelta(days=30)


def test_extended_expiry_negative_shortens():
    now = utcnow()
    future = now + timedelta(days=30)
    # −10 dní skráti zostatok; výsledok je stále v budúcnosti.
    assert _extended_expiry(future, -10, now) == future - timedelta(days=10)
    # −40 dní posunie expiráciu do minulosti (PLUS by skončil).
    assert _extended_expiry(future, -40, now) < now


def test_mrr_computation():
    # 2 mesačné + 1 ročné → 2*4.99 + 39.99/12
    expected = round(2 * PRICE_MONTHLY_EUR + 1 * (PRICE_ANNUAL_EUR / 12.0), 2)
    assert _mrr(2, 1) == expected
    assert _mrr(0, 0) == 0.0
