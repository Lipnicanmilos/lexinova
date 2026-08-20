"""Cookieless analytika: vypnutá bez env, CSP a wrapper na ciele funnelu."""
import pytest

import app.main as main_module
import app.services.runtime as runtime

# Stránky, na ktorých chceme merať — verejné aj kroky funnelu v aplikácii.
TRACKED_PAGES = ["/", "/pricing", "/register", "/login", "/demo", "/blog", "/privacy"]


@pytest.mark.parametrize("path", TRACKED_PAGES)
def test_stranky_maju_wrapper_lexitrack(client, path):
    """`lexiTrack` musí existovať všade, inak by volania v šablónach padali."""
    assert "window.lexiTrack" in client.get(path).text


@pytest.mark.parametrize("path", TRACKED_PAGES)
def test_bez_env_sa_analytika_nevykresli(client, path):
    """Bez `ANALYTICS_DOMAIN` (lokál, testy) neodchádzajú žiadne dáta."""
    text = client.get(path).text
    assert "plausible.io" not in text
    assert "data-domain" not in text


def test_csp_neobsahuje_analytiku_ked_je_vypnuta(client):
    csp = client.get("/").headers["Content-Security-Policy"]
    assert "plausible" not in csp


def test_admin_nema_analytiku(client):
    """Interný nástroj sa zámerne nemeria (a nemá partial)."""
    from pathlib import Path

    admin = Path("app/templates/admin.html").read_text(encoding="utf-8")
    assert "partials/analytics.html" not in admin


def test_origin_pre_csp_sa_odvodi_zo_src(monkeypatch):
    monkeypatch.setattr(runtime, "ANALYTICS_DOMAIN", "lexinova.fun")
    monkeypatch.setattr(runtime, "ANALYTICS_SRC", "https://plausible.io/js/script.js")
    assert runtime._analytics_origin() == "https://plausible.io"


def test_origin_podporuje_self_hosted_instanciu(monkeypatch):
    monkeypatch.setattr(runtime, "ANALYTICS_DOMAIN", "lexinova.fun")
    monkeypatch.setattr(runtime, "ANALYTICS_SRC", "https://stats.example.com/js/script.js")
    assert runtime._analytics_origin() == "https://stats.example.com"


def test_origin_je_prazdny_ked_je_analytika_vypnuta(monkeypatch):
    monkeypatch.setattr(runtime, "ANALYTICS_DOMAIN", "")
    assert runtime._analytics_origin() == ""


def test_relativny_src_nerozbije_csp(monkeypatch):
    """Preklep v env nesmie vyrobiť nevalidnú CSP — radšej sa analytika vynechá."""
    monkeypatch.setattr(runtime, "ANALYTICS_DOMAIN", "lexinova.fun")
    monkeypatch.setattr(runtime, "ANALYTICS_SRC", "/js/script.js")
    assert runtime._analytics_origin() == ""


def test_csp_a_preconnect_hovoria_o_tom_istom_hostovi(monkeypatch):
    """`preconnect` v šablóne a `script-src` v CSP musia sedieť.

    Keby sa rozišli, prehliadač by otvoril spojenie na host, ktorý mu CSP
    vzápätí zakáže použiť — teda réžia navyše a analytika aj tak zablokovaná.
    Obe hodnoty preto vychádzajú z jedného `runtime.ANALYTICS_ORIGIN`.
    """
    assert main_module._ANALYTICS.strip() == runtime.ANALYTICS_ORIGIN
    assert runtime.templates.env.globals["analytics_origin"] == runtime.ANALYTICS_ORIGIN
