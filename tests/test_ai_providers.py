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
    assert "gemini-3.8-flash" in candidates and "gemma-4-31b-it" in candidates
    assert not any(m.startswith("gemini-2") for m in candidates)


def test_retired_gemini_from_the_environment_is_ignored(monkeypatch):
    """Na Cloud Rune môže v GEMINI_MODEL ostať 2.5 Flash. Ten Google vypína,
    tak by bol len ďalší zbytočný request pred lepším modelom."""
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    assert acs.gemini_model() == "gemini-3.6-flash"
    assert acs._candidate_gemini_models("gemini-2.5-flash")[0] == "gemini-3.6-flash"
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.6-flash")
    assert acs.gemini_model() == "gemini-3.6-flash"


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


def test_gemini_thinks_as_little_as_each_model_allows():
    assert acs.gemini_generation_config("gemini-2.5-flash", {"temperature": 0.4}) == {
        "temperature": 0.4, "thinkingConfig": {"thinkingBudget": 0},
    }
    # 3.8 Flash MINIMAL nepozná, najnižšie je LOW.
    assert acs.gemini_generation_config("gemini-3.8-flash", {})["thinkingConfig"] == {"thinkingLevel": "low"}
    assert acs.gemini_generation_config("gemini-3.6-flash", {})["thinkingConfig"] == {"thinkingLevel": "minimal"}
    assert acs.gemini_generation_config("gemma-4-31b-it", {})["thinkingConfig"] == {"thinkingLevel": "minimal"}
    # 2.5 Pro premýšľanie vypnúť nevie — nič nepridávame.
    assert acs.gemini_generation_config("gemini-2.5-pro", {}) == {}


def test_set_generation_sends_thinking_off_to_gemini(monkeypatch):
    sent = []
    ok = _Response(200, {"candidates": [{"content": {"parts": [{"text": '{"words": []}'}]}}]})
    monkeypatch.setattr(acs.httpx, "AsyncClient", _fake_client([ok], sent))
    asyncio.run(acs._ask_gemini(api_key="k", model="gemini-3.8-flash", full_prompt="p"))
    assert sent[0]["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}


def test_rejected_thinking_setting_is_retried_without_it(monkeypatch):
    """Keby Google úroveň premýšľania pre model odmietol (400), volanie nesmie
    padnúť na ďalší model — zopakuje sa raz bez nej."""
    sent = []
    ok = _Response(200, {"candidates": [{"content": {"parts": [{"text": '{"words": []}'}]}}]})
    monkeypatch.setattr(acs.httpx, "AsyncClient", _fake_client([_Response(400), ok], sent))
    asyncio.run(acs._ask_gemini(api_key="k", model="gemini-3.8-flash", full_prompt="p"))
    assert len(sent) == 2
    assert "thinkingConfig" in sent[0]["generationConfig"]
    assert "thinkingConfig" not in sent[1]["generationConfig"]


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


def test_gemma_thought_part_does_not_hide_the_answer(monkeypatch):
    """Gemma 4 vracia najprv prázdnu časť s premýšľaním a odpoveď až za ňou
    (tak odpovedala 19. 11. 2026). Prvá časť nesmie byť celá odpoveď."""
    sent = []
    body = {"candidates": [{"content": {"parts": [
        {"text": "", "thought": True},
        {"text": '{"category_name": "Cestovanie", "words": [{"original_word": "travel", "translation": "cestovať"}]}'},
    ]}}]}
    monkeypatch.setattr(acs.httpx, "AsyncClient", _fake_client([_Response(200, body)], sent))
    data = asyncio.run(acs._ask_gemini(api_key="k", model="gemma-4-31b-it", full_prompt="p"))
    assert data["words"][0]["original_word"] == "travel"
    assert acs.gemini_text({"candidates": [{"content": {"parts": [
        {"text": "uvazujem", "thought": True}, {"text": "Ahoj"}]}}]}) == "Ahoj"
