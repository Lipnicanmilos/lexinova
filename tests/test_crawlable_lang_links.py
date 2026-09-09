# -*- coding: utf-8 -*-
"""Na anglické verzie stránok musí viesť odkaz, ktorý crawler prejde.

Prepínač jazyka bol `<button data-lang="en">` a prepínal sa výhradne
skriptom, takže na `/en/*` neviedol z webu ani jeden `<a href>`. Google ich
poznal nanajvýš zo sitemapy — najslabší možný signál — a Search Console
ukazovala mesiace nulový posun. Navyše `/en` odkazovala len na slovenské
URL, takže bola slepou uličkou v oboch smeroch.
"""
import re

import pytest

# (SK cesta, EN cesta) pre verejné stránky, ktoré majú v šablóne prepínač.
# /demo tu chýba zámerne: je to holá ukážka kartičiek bez navigačnej lišty,
# takže prepínač nemá kam ísť. Na /en/demo sa crawler dostane z navigácie /en.
DVOJICE = [
    ("/", "/en"),
    ("/pricing", "/en/pricing"),
    ("/pre-ucitelov", "/en/pre-ucitelov"),
    ("/register", "/en/register"),
    ("/terms", "/en/terms"),
    ("/privacy", "/en/privacy"),
    ("/refunds", "/en/refunds"),
]


def _prepinac(html):
    """Vráti {jazyk: href} z prepínača jazyka."""
    return {
        m.group("lang"): m.group("href")
        for m in re.finditer(
            r'<a [^>]*class="[^"]*lang-btn[^"]*"[^>]*href="(?P<href>[^"]*)"'
            r'[^>]*data-lang="(?P<lang>sk|en)"',
            html,
        )
    }


@pytest.mark.parametrize("sk,en", DVOJICE)
def test_prepinac_je_odkaz_nie_tlacidlo(client, sk, en):
    """Jadro opravy: bez <a href> crawler na EN vetvu nemá ako prísť."""
    for cesta in (sk, en):
        html = client.get(cesta).text
        assert not re.search(r"<button[^>]*data-lang=", html), (
            f"{cesta}: prepínač ostal <button>, crawler ho neprejde"
        )
        assert _prepinac(html) == {"sk": sk, "en": en}, (
            f"{cesta}: prepínač nemieri na jazykové náprotivky"
        )


@pytest.mark.parametrize("sk,en", DVOJICE)
def test_aktivny_jazyk_urcuje_server(client, sk, en):
    """Jazyk je daný URL, netreba naň čakať na skript stránky."""
    for cesta, aktivny in ((sk, "sk"), (en, "en")):
        html = client.get(cesta).text
        for m in re.finditer(
            r'<a (?P<attrs>[^>]*class="[^"]*lang-btn[^"]*"[^>]*)>', html
        ):
            attrs = m.group("attrs")
            jazyk = re.search(r'data-lang="(sk|en)"', attrs).group(1)
            ma_active = "active" in re.search(r'class="([^"]*)"', attrs).group(1).split()
            assert ma_active == (jazyk == aktivny), (
                f"{cesta}: {jazyk} má byť {'aktívny' if jazyk == aktivny else 'neaktívny'}"
            )


def test_en_stranka_odkazuje_do_en_vetvy(client):
    """`/en` viedla výhradne na slovenské URL — slepá ulička."""
    html = client.get("/en").text
    odkazy = set(re.findall(r'<a [^>]*href="(/[^"]*)"', html))
    for ocakavany in ("/en/pricing", "/en/demo", "/en/register", "/blog/en"):
        assert ocakavany in odkazy, f"/en neodkazuje na {ocakavany}"
    # Jediný slovenský odkaz smie byť prepínač jazyka a /slovicka, ktoré
    # anglickú verziu nemá.
    assert "/pricing" not in odkazy and "/blog" not in odkazy


def test_en_demo_je_dosiahnutelne_hoci_nema_prepinac(client):
    """Šablóna /demo prepínač nemá — odkaz naň musí dať navigácia /en."""
    odkazy = set(re.findall(r'<a [^>]*href="(/[^"]*)"', client.get("/en").text))
    assert "/en/demo" in odkazy


def test_sk_stranka_ponuka_crawlovatelny_odkaz_na_en(client):
    """Presne ten odkaz, ktorý na webe chýbal."""
    assert '<a ' in client.get("/").text
    odkazy = set(re.findall(r'<a [^>]*href="(/[^"]*)"', client.get("/").text))
    assert "/en" in odkazy


def test_staticke_subory_ostavaju_nedotknute(client):
    """Prepis odkazov beží nad celým HTML, nesmie siahnuť na assety."""
    html = client.get("/en").text
    assert 'href="/manifest.json"' in html
    assert 'href="/static/css/design-system.css' in html
    assert "/en/static/" not in html and "/en/manifest.json" not in html
