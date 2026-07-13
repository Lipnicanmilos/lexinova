"""Stabilita AI reťazca — Gemini 429 kaskáda, refund kvóty, fallback na Groq.

Všetko mockované (žiadne sieťové volania). Overuje opravy z 2026-07-13:
- 429 od Gemini zastaví ďalšie pokusy OKAMŽITE (nie 4 modely × 2 API = 8 requestov)
  a prepne na ďalšieho providera.
- Zlyhanie všetkých providerov vráti Free účtu odpočítanú AI kvótu.
- Vyčerpaná kvóta providera sa mapuje na HTTP 429 (nie 502).
"""
import asyncio

import pytest

from app.models.user import User
from app.services.ai_category_service import (
    GeminiRateLimited,
    generate_category_and_words_from_image_gemini,
    generate_category_and_words_gemini,
)
from app.services.limits import consume_ai_quota, refund_ai_quota


def _register(client, email):
    client.post("/api/v1/register", json={"email": email, "password": "Abcdef12"})


def _get_user(db_factory, email):
    db = db_factory()
    try:
        return db.query(User).filter(User.email == email).first()
    finally:
        db.close()


def _fake_generated():
    return {
        "category_name": "Cestovanie",
        "category_description": "Slovíčka na cesty",
        "words": [
            {"original_word": "travel", "translation": "cestovať", "language_from": "en", "language_to": "sk"},
            {"original_word": "airport", "translation": "letisko", "language_from": "en", "language_to": "sk"},
        ],
    }


class _FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code

    def json(self):
        return {}


def _mock_gemini_http(monkeypatch, status_code, calls):
    """Nahradí httpx.AsyncClient v AI službe — každý POST vráti daný status."""

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, **kwargs):
            calls.append(url)
            return _FakeResponse(status_code)

    monkeypatch.setattr("app.services.ai_category_service.httpx.AsyncClient", _FakeClient)


# --- Služba: 429 zastaví kaskádu okamžite -----------------------------------


def test_gemini_429_stops_after_first_request(monkeypatch):
    """Kvóta je spoločná pre projekt — pri 429 nesmie odísť 8 requestov, len 1."""
    calls = []
    _mock_gemini_http(monkeypatch, 429, calls)

    with pytest.raises(GeminiRateLimited):
        asyncio.run(
            generate_category_and_words_gemini(
                api_key="k", model="gemini-2.5-flash", prompt="travel words",
                language_from="en", language_to="sk", count=10,
            )
        )
    assert len(calls) == 1


def test_image_gemini_429_stops_after_first_request(monkeypatch):
    """Fotková cesta mala rovnakú kaskádu — aj tá musí skončiť po 1. requeste."""
    calls = []
    _mock_gemini_http(monkeypatch, 429, calls)

    with pytest.raises(GeminiRateLimited):
        asyncio.run(
            generate_category_and_words_from_image_gemini(
                api_key="k", model="gemini-2.5-flash", image_b64="aGk=",
                media_type="image/png", language_from="en", language_to="sk",
                max_count=30,
            )
        )
    assert len(calls) == 1


def test_gemini_404_still_tries_all_candidates(monkeypatch):
    """404 = model neexistuje — skúšanie ďalších modelov je tu žiaduce
    a chybová hláška má obsahovať VŠETKY pokusy, nie len posledný."""
    calls = []
    _mock_gemini_http(monkeypatch, 404, calls)

    with pytest.raises(RuntimeError) as excinfo:
        asyncio.run(
            generate_category_and_words_gemini(
                api_key="k", model="gemini-2.5-flash", prompt="travel words",
                language_from="en", language_to="sk", count=10,
            )
        )
    assert not isinstance(excinfo.value, GeminiRateLimited)
    assert len(calls) == 8  # 4 modely × 2 verzie API
    # zoznam chýb nesie všetky kandidátske modely (nie len posledný)
    assert "gemini-2.5-flash" in str(excinfo.value)
    assert "gemini-2.0-flash-lite" in str(excinfo.value)


# --- Limity: refund kvóty ----------------------------------------------------


def test_refund_ai_quota_restores_use(db_factory, client):
    _register(client, "quota_refund@example.com")
    db = db_factory()
    try:
        user = db.query(User).filter(User.email == "quota_refund@example.com").first()
        consume_ai_quota(db, user)
        assert user.ai_uses_count == 1
        refund_ai_quota(db, user)
        assert user.ai_uses_count == 0
        # refund pri nule nesmie ísť do mínusu
        refund_ai_quota(db, user)
        assert user.ai_uses_count == 0
    finally:
        db.close()


# --- Endpoint: fallback a refund ---------------------------------------------


def test_ai_create_falls_back_to_groq_on_gemini_quota(client, db_factory, monkeypatch):
    """429 od Gemini → Groq prevezme request a používateľ dostane slovíčka."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    _register(client, "ai_fallback@example.com")

    async def _gemini_rate_limited(**kwargs):
        raise GeminiRateLimited("kvóta vyčerpaná")

    async def _groq_ok(**kwargs):
        return _fake_generated()

    monkeypatch.setattr(
        "app.routers.categories.generate_category_and_words_gemini", _gemini_rate_limited
    )
    monkeypatch.setattr(
        "app.routers.categories.generate_category_and_words_groq", _groq_ok
    )

    res = client.post(
        "/api/v1/categories/ai-create",
        json={"prompt": "travel vocabulary", "count": 10},
    )
    assert res.status_code == 200, res.text
    assert res.json()["inserted_words"] == 2
    # úspešné generovanie = kvóta ostáva započítaná
    assert _get_user(db_factory, "ai_fallback@example.com").ai_uses_count == 1


def test_ai_create_maps_quota_exhaustion_to_429_and_refunds(client, db_factory, monkeypatch):
    """Gemini 429 a Groq nie je nakonfigurovaný → 429 (nie 502) + kvóta vrátená."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    monkeypatch.setenv("GROQ_API_KEY", "")  # bez fallbacku
    _register(client, "ai_429@example.com")

    async def _gemini_rate_limited(**kwargs):
        raise GeminiRateLimited("kvóta vyčerpaná")

    monkeypatch.setattr(
        "app.routers.categories.generate_category_and_words_gemini", _gemini_rate_limited
    )

    res = client.post(
        "/api/v1/categories/ai-create",
        json={"prompt": "travel vocabulary", "count": 10},
    )
    assert res.status_code == 429
    assert "kvóta" in res.json()["detail"].lower()
    # zlyhaný pokus nesmie Free účtu ukrojiť z denného limitu
    assert _get_user(db_factory, "ai_429@example.com").ai_uses_count == 0


def test_ai_create_refunds_quota_when_all_providers_fail(client, db_factory, monkeypatch):
    """Všetci provideri padnú (nie kvóta) → 502 + kvóta vrátená."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    _register(client, "ai_502@example.com")

    async def _boom(**kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(
        "app.routers.categories.generate_category_and_words_gemini", _boom
    )
    monkeypatch.setattr(
        "app.routers.categories.generate_category_and_words_groq", _boom
    )

    res = client.post(
        "/api/v1/categories/ai-create",
        json={"prompt": "travel vocabulary", "count": 10},
    )
    assert res.status_code == 502
    assert _get_user(db_factory, "ai_502@example.com").ai_uses_count == 0
