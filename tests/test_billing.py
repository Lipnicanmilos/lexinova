"""Platby (Lemon Squeezy) — checkout, stav predplatného, webhook."""
import hashlib
import hmac
import json


def _sign(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def test_checkout_requires_auth(client):
    r = client.post("/api/v1/checkout", json={"plan": "monthly"})
    assert r.status_code in (401, 403)


def test_checkout_not_configured_returns_503(client):
    client.post("/api/v1/register", json={"email": "pay@example.com", "password": "Abcdef12"})
    r = client.post("/api/v1/checkout", json={"plan": "monthly"})
    assert r.status_code == 503


def test_checkout_invalid_plan(client):
    client.post("/api/v1/register", json={"email": "plan@example.com", "password": "Abcdef12"})
    r = client.post("/api/v1/checkout", json={"plan": "weekly"})
    assert r.status_code == 400


def test_subscription_status_default(client):
    client.post("/api/v1/register", json={"email": "sub@example.com", "password": "Abcdef12"})
    data = client.get("/api/v1/subscription").json()
    assert data["is_plus"] is False
    assert data["status"] is None


def test_webhook_rejects_invalid_signature(client):
    r = client.post("/api/webhooks/lemonsqueezy", content=b"{}", headers={"X-Signature": "bad"})
    assert r.status_code == 401


def test_webhook_activates_plus(client, monkeypatch):
    monkeypatch.setenv("LEMONSQUEEZY_WEBHOOK_SECRET", "testsecret")
    reg = client.post("/api/v1/register", json={"email": "wh@example.com", "password": "Abcdef12"})
    uid = reg.json()["user"]["id"]

    body = {
        "meta": {"event_name": "subscription_created", "custom_data": {"user_id": str(uid)}},
        "data": {
            "id": "sub_123",
            "attributes": {
                "status": "active",
                "renews_at": "2099-01-01T00:00:00Z",
                "customer_id": 99,
                "variant_id": "v_month",
            },
        },
    }
    raw = json.dumps(body).encode()
    r = client.post(
        "/api/webhooks/lemonsqueezy", content=raw, headers={"X-Signature": _sign(raw, "testsecret")}
    )
    assert r.status_code == 200

    data = client.get("/api/v1/subscription").json()
    assert data["is_plus"] is True
    assert data["status"] == "active"
    assert data["expires_at"] is not None


def test_webhook_expired_deactivates_plus(client, monkeypatch):
    monkeypatch.setenv("LEMONSQUEEZY_WEBHOOK_SECRET", "testsecret")
    reg = client.post("/api/v1/register", json={"email": "exp@example.com", "password": "Abcdef12"})
    uid = reg.json()["user"]["id"]

    body = {
        "meta": {"event_name": "subscription_expired", "custom_data": {"user_id": str(uid)}},
        "data": {"id": "sub_999", "attributes": {"status": "expired", "ends_at": "2020-01-01T00:00:00Z"}},
    }
    raw = json.dumps(body).encode()
    r = client.post(
        "/api/webhooks/lemonsqueezy", content=raw, headers={"X-Signature": _sign(raw, "testsecret")}
    )
    assert r.status_code == 200
    assert client.get("/api/v1/subscription").json()["is_plus"] is False
