"""OAuth state prežije prepis/zmazanie session cookie.

Regresia: súbežná požiadavka (predcache service workera, iný tab) prepísala
session cookie zo staršieho snapshotu, čím z nej vypadol authlib state
a Google login padol na "mismatching_state: CSRF Warning!".
"""
import time

import pytest
from starlette.requests import Request

from app.routers.auth import (
    OAUTH_STATE_COOKIE,
    OAUTH_STATE_TTL,
    _restore_oauth_state,
    _state_signer,
)

STATE_KEY = "_state_google_abc123"
STATE_VALUE = {
    "data": {"redirect_uri": "https://lexinova.fun/auth/google/callback", "nonce": "n1"},
    "exp": time.time() + 3600,
}


def _request(cookie_value=None, session=None, query_string=b""):
    headers = []
    if cookie_value is not None:
        headers.append((b"cookie", f"{OAUTH_STATE_COOKIE}={cookie_value}".encode()))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/auth/google/callback",
            "query_string": query_string,
            "headers": headers,
            "session": session if session is not None else {},
        }
    )


def test_state_restored_when_session_cookie_lost():
    signed = _state_signer.dumps({STATE_KEY: STATE_VALUE})
    request = _request(signed)  # session prázdna — cookie ju medzitým prepísala

    assert _restore_oauth_state(request) == "cookie"

    assert request.session[STATE_KEY] == STATE_VALUE


def test_session_wins_when_state_still_present():
    signed = _state_signer.dumps({STATE_KEY: STATE_VALUE})
    live = {"data": {"redirect_uri": "x", "nonce": "live"}, "exp": time.time() + 3600}
    request = _request(signed, session={STATE_KEY: live}, query_string=b"state=abc123")

    assert _restore_oauth_state(request) == "session"

    assert request.session[STATE_KEY] == live


@pytest.mark.parametrize(
    "cookie,expected",
    [(None, "missing"), ("tampered.value.here", "invalid")],
)
def test_missing_or_invalid_cookie_is_ignored(cookie, expected):
    request = _request(cookie)

    assert _restore_oauth_state(request) == expected

    assert request.session == {}


def test_expired_cookie_is_ignored(monkeypatch):
    """Cookie staršia ako TTL sa zahodí — flow padne na login, nie na 500."""
    import app.routers.auth as auth_module

    signed = _state_signer.dumps({STATE_KEY: STATE_VALUE})
    request = _request(signed)

    # Záporný max_age = podpis je "starší" než povolené → SignatureExpired.
    original_loads = auth_module._state_signer.loads
    monkeypatch.setattr(
        auth_module._state_signer,
        "loads",
        lambda value, max_age=None: original_loads(value, max_age=-OAUTH_STATE_TTL),
    )

    assert _restore_oauth_state(request) == "expired"

    assert request.session == {}
