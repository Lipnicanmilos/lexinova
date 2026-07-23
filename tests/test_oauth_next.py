"""Cieľ ?next= prežije Google OAuth flow.

Regresia: žiak prišiel cez zdieľací link (/s/{kód}) alebo kód triedy (/c/{kód}),
prihlásil sa cez Google a skončil na /dashboard bez sady — `next` fungoval len
pri prihlásení e-mailom a heslom.
"""
import pytest
from starlette.requests import Request

from app.routers.auth import (
    OAUTH_NEXT_COOKIE,
    _next_signer,
    _restore_next,
    _safe_next,
    _signer,
)


def _request(cookie_value=None, session=None):
    headers = []
    if cookie_value is not None:
        headers.append((b"cookie", f"{OAUTH_NEXT_COOKIE}={cookie_value}".encode()))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/auth/google/callback",
            "query_string": b"",
            "headers": headers,
            "session": session if session is not None else {},
        }
    )


@pytest.mark.parametrize("value", ["/s/ABC123", "/c/XYZ789", "/dashboard", "/blog?x=1"])
def test_interna_cesta_prejde(value):
    assert _safe_next(value) == value


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "//evil.example",           # protocol-relative URL = cudzia doména
        "https://evil.example",
        "/\\evil.example",          # niektoré prehliadače čítajú ako //
        "javascript:alert(1)",
        "/ok\nLocation: /zle",      # pokus o vloženie hlavičky
    ],
)
def test_open_redirect_je_odmietnuty(value):
    assert _safe_next(value) is None


def test_next_zo_session():
    request = _request(session={"oauth_next": "/s/ABC123"})

    assert _restore_next(request) == "/s/ABC123"
    # Spotrebovaný cieľ nesmie ostať v session — inak by presmeroval aj ďalší,
    # celkom nesúvisiaci pokus o prihlásenie.
    assert "oauth_next" not in request.session


def test_cookie_zaskoci_ked_session_neprezije():
    request = _request(_next_signer.dumps("/c/XYZ789"))

    assert _restore_next(request) == "/c/XYZ789"


def test_bez_cookie_aj_session_je_ciel_prazdny():
    assert _restore_next(_request()) is None


def test_podvrhnuta_cookie_sa_ignoruje():
    assert _restore_next(_request("tampered.value.here")) is None


def test_cookie_s_cudzou_domenou_sa_ignoruje():
    """Aj správne podpísaná cookie prejde kontrolou cesty."""
    assert _restore_next(_request(_next_signer.dumps("https://evil.example"))) is None


def _finalize(client, payload):
    token = _signer.dumps(payload)
    return client.get(f"/auth/finalize?t={token}", follow_redirects=False)


SESSION_USER = {"id": 1, "email": "z@example.com", "name": "Zak", "is_plus": False}


def test_finalize_presmeruje_na_next(client):
    response = _finalize(client, {"user": SESSION_USER, "next": "/s/ABC123"})

    assert response.status_code == 303
    assert response.headers["location"] == "/s/ABC123"


def test_finalize_bez_next_ide_na_dashboard(client):
    response = _finalize(client, {"user": SESSION_USER, "next": None})

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


def test_finalize_odmietne_cudziu_domenu_aj_v_podpisanom_tokene(client):
    """Podpis potvrdzuje pôvod, nie neškodnosť — cieľ sa overuje aj tu."""
    response = _finalize(client, {"user": SESSION_USER, "next": "https://evil.example"})

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


def test_finalize_zvladne_token_stareho_tvaru(client):
    """Počas deployu môže doraziť token vydaný predošlou verziou (holý user dict)."""
    response = _finalize(client, SESSION_USER)

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"
