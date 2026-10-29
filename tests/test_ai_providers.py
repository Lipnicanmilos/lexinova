"""Bezplatní AI poskytovatelia — keď model vypnú alebo minú kvótu.

29. 10. 2026 na produkcii: Groq vracal 404 (llama-3.3-70b-versatile vypnutý
16. 8. 2026), Gemini 2.5-flash-lite 404 (len pre staršie projekty) a httpx
logoval Gemini kľúč v adrese. Tieto testy strážia, že sa to nevráti.
"""
import asyncio
import logging

import pytest

from app.services import ai_category_service as acs


class _Response:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._body


def _fake_client(responses, sent):
    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            sent.append(json)
            return responses.pop(0)

    return _Client


def test_groq_retired_model_falls_back_to_next(monkeypatch):
    sent = []
    ok = _Response(200, {"choices": [{"message": {"content": "Hi!"}}]})
    monkeypatch.setattr(acs.httpx, "AsyncClient", _fake_client([_Response(404), ok], sent))
    data = asyncio.run(acs.post_groq_chat(
        api_key="k", model="llama-3.3-70b-versatile", payload={"messages": []}, timeout_s=5,
    ))
    assert data["choices"][0]["message"]["content"] == "Hi!"
    assert [p["model"] for p in sent] == ["llama-3.3-70b-versatile", "openai/gpt-oss-120b"]
    # gpt-oss premýšľa — nízke úsilie a bez úvah v odpovedi, inak zje limit tokenov.
    assert sent[1]["reasoning_effort"] == "low" and sent[1]["include_reasoning"] is False
    assert "reasoning_effort" not in sent[0]


def test_groq_429_is_rate_limited(monkeypatch):
    monkeypatch.setattr(acs.httpx, "AsyncClient", _fake_client([_Response(429)], []))
    with pytest.raises(acs.GeminiRateLimited):
        asyncio.run(acs.post_groq_chat(api_key="k", model="openai/gpt-oss-120b", payload={}, timeout_s=5))


def test_gemini_fallbacks_skip_shut_down_models():
    candidates = acs._candidate_gemini_models("gemini-3.5-flash-lite")
    assert candidates[0] == "gemini-3.5-flash-lite"
    assert "gemini-2.5-flash" in candidates
    assert not any(m.startswith("gemini-2.0") for m in candidates)


def test_httpx_does_not_log_urls_with_keys():
    from app.services import runtime  # noqa: F401  (konfigurácia logov pri importe)
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
