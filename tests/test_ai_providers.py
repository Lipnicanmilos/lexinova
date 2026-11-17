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
    def __init__(self, status, body=None, text=""):
        self.status_code = status
        self._body = body or {}
        self.text = text

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


_TOO_LARGE = ("Request too large for model `openai/gpt-oss-120b` on tokens per minute (TPM): "
              "Limit 8000, Requested 9300, please reduce your message size and try again.")
_OK = {"choices": [{"message": {"content": "{}"}}]}


def test_groq_413_retries_with_smaller_max_tokens(monkeypatch):
    """Groq ráta do stropu tokenov za minútu aj `max_tokens` — po 413 sa
    to isté zopakuje s menším `max_tokens`, nie chyba."""
    sent = []
    responses = [_Response(413, text=_TOO_LARGE), _Response(200, _OK)]
    monkeypatch.setattr(acs.httpx, "AsyncClient", _fake_client(responses, sent))
    asyncio.run(acs.post_groq_chat(
        api_key="k", model="openai/gpt-oss-120b", payload={"messages": [], "max_tokens": 8192}, timeout_s=5,
    ))
    assert [p["model"] for p in sent] == ["openai/gpt-oss-120b", "openai/gpt-oss-120b"]
    assert sent[1]["max_tokens"] == 8192 - 1300 - 200


def test_groq_413_without_room_goes_to_next_model(monkeypatch):
    sent = []
    responses = [_Response(413, text="too large"), _Response(200, _OK)]
    monkeypatch.setattr(acs.httpx, "AsyncClient", _fake_client(responses, sent))
    asyncio.run(acs.post_groq_chat(
        api_key="k", model="openai/gpt-oss-120b", payload={"messages": [], "max_tokens": 6500}, timeout_s=5,
    ))
    assert [p["model"] for p in sent] == ["openai/gpt-oss-120b", "llama-3.1-8b-instant"]


def test_set_generation_fits_groq_free_limit(monkeypatch):
    """Strop odpovede + prompt sa zmestí pod 8000 tokenov/min bezplatného gpt-oss-120b."""
    sent = []
    monkeypatch.setattr(acs.httpx, "AsyncClient", _fake_client([_Response(200, _OK)], sent))
    asyncio.run(acs._ask_groq(api_key="k", model="openai/gpt-oss-120b", full_prompt="p"))
    assert sent[0]["max_tokens"] <= 7000


def test_gemini_25_flash_does_not_think():
    assert acs.gemini_generation_config("gemini-2.5-flash", {"temperature": 0.4}) == {
        "temperature": 0.4, "thinkingConfig": {"thinkingBudget": 0},
    }
    assert "thinkingConfig" in acs.gemini_generation_config("models/gemini-2.5-flash-lite", {})
    # 2.5 Pro premýšľanie vypnúť nevie, 3.x má iný parameter — tým nič nepridávame.
    assert acs.gemini_generation_config("gemini-2.5-pro", {}) == {}
    assert acs.gemini_generation_config("gemini-3.5-flash-lite", {}) == {}


def test_set_generation_sends_thinking_off_to_gemini(monkeypatch):
    sent = []
    ok = _Response(200, {"candidates": [{"content": {"parts": [{"text": '{"words": []}'}]}}]})
    monkeypatch.setattr(acs.httpx, "AsyncClient", _fake_client([ok], sent))
    asyncio.run(acs._ask_gemini(api_key="k", model="gemini-2.5-flash", full_prompt="p"))
    assert sent[0]["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}


def test_gemini_timeout_does_not_try_every_model(monkeypatch):
    """Timeout na jednom modeli = rovno von (volajúci skúsi Groq), nie ďalších
    päť modelov po minúte."""
    calls = []

    class _Slow:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            calls.append(url)
            raise acs.httpx.ReadTimeout("slow")

    monkeypatch.setattr(acs.httpx, "AsyncClient", _Slow)
    with pytest.raises(acs.httpx.TransportError):
        asyncio.run(acs._ask_gemini(api_key="k", model="gemini-2.5-flash", full_prompt="p"))
    assert len(calls) == 1


def test_groq_image_retired_model_falls_back_to_vision_model(monkeypatch):
    """17. 11. 2026: vision model na Groq vrátil 404 a tvorba z fotky padla bez
    pokusu o iný model. Záloha musí byť model, čo vidí obrázky (nie gpt-oss)."""
    sent = []
    ok = _Response(200, {"choices": [{"message": {"content": '{"category_name": "X", "words": []}'}}]})
    not_found = _Response(404, text='{"error":{"code":"model_not_found"}}')
    monkeypatch.setattr(acs.httpx, "AsyncClient", _fake_client([not_found, ok], sent))
    monkeypatch.setattr(acs, "_parse_json_text", lambda text: {"raw": text})
    asyncio.run(acs.generate_category_and_words_from_image_groq(
        api_key="k", model="qwen/qwen3.6-27b", image_b64="aGk=", media_type="image/png",
        language_from="sk", language_to="en", max_count=10,
    ))
    assert [p["model"] for p in sent] == ["qwen/qwen3.6-27b", acs.GROQ_VISION_FALLBACK_MODELS[0]]
    assert sent[1]["messages"][0]["content"][1]["type"] == "image_url"


def test_groq_no_model_error_includes_reason(monkeypatch):
    """Z logu musí byť vidno, prečo Groq odmietol (telo odpovede), nie len 404."""
    responses = [_Response(404, text="model_not_found") for _ in acs.GROQ_VISION_FALLBACK_MODELS + ("x",)]
    monkeypatch.setattr(acs.httpx, "AsyncClient", _fake_client(responses, []))
    with pytest.raises(RuntimeError, match="model_not_found"):
        asyncio.run(acs.post_groq_chat(
            api_key="k", model="x", payload={}, timeout_s=5,
            fallback_models=acs.GROQ_VISION_FALLBACK_MODELS,
        ))
