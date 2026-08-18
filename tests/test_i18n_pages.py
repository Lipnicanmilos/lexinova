"""Verejné stránky v dvoch jazykoch na dvoch URL.

Crawler nemá localStorage, takže jazyk musí byť rozhodnutý na serveri:
`/` po slovensky (primárny trh), `/en` po anglicky, navzájom prepojené cez
hreflang. Predtým videl Google na homepage vždy len angličtinu.
"""
import re

import pytest

from app.routers.pages import PUBLIC_LOCALIZED_PAGES
from app.services.i18n_html import localize

SK_PATHS = list(PUBLIC_LOCALIZED_PAGES)


def _en_path(sk_path: str) -> str:
    return ("/en" + sk_path).rstrip("/")


def _attr(html: str, pattern: str):
    m = re.search(pattern, html, re.I | re.S)
    return m.group(1).strip() if m else None


@pytest.mark.parametrize("sk_path", SK_PATHS)
def test_slovenska_verzia_je_po_slovensky(client, sk_path):
    html = client.get(sk_path).text
    assert _attr(html, r'<html[^>]*\slang="([^"]+)"') == "sk"
    assert _attr(html, r'<link[^>]*rel="canonical"[^>]*href="([^"]+)"').endswith(sk_path)


@pytest.mark.parametrize("sk_path", SK_PATHS)
def test_anglicka_verzia_je_po_anglicky(client, sk_path):
    en_path = _en_path(sk_path)
    html = client.get(en_path).text
    assert _attr(html, r'<html[^>]*\slang="([^"]+)"') == "en"
    assert _attr(html, r'<link[^>]*rel="canonical"[^>]*href="([^"]+)"').endswith(en_path)


@pytest.mark.parametrize("sk_path", SK_PATHS)
def test_obe_verzie_na_seba_ukazuju(client, sk_path):
    """Bez hreflang by Google mohol jazykové verzie vyhodnotiť ako duplicitu."""
    en_path = _en_path(sk_path)
    for path in (sk_path, en_path):
        html = client.get(path).text
        alternates = dict(re.findall(r'hreflang="([^"]+)" href="([^"]+)"', html))
        assert alternates["sk"].endswith(sk_path)
        assert alternates["en"].endswith(en_path)
        # x-default mieri na SK — primárny trh je SK/CZ.
        assert alternates["x-default"] == alternates["sk"]


@pytest.mark.parametrize("sk_path", SK_PATHS)
def test_kazda_verzia_ma_prave_jeden_h1(client, sk_path):
    for path in (sk_path, _en_path(sk_path)):
        html = client.get(path).text
        assert len(re.findall(r"<h1[\s>]", html, re.I)) == 1, path


def test_titulok_a_popis_su_v_jazyku_stranky(client):
    sk = client.get("/").text
    en = client.get("/en").text
    assert "Tréner slovíčok" in _attr(sk, r"<title[^>]*>(.*?)</title>")
    assert "Vocabulary Trainer" in _attr(en, r"<title[^>]*>(.*?)</title>")
    assert "Tréner slovíčok" in _attr(
        sk, r'<meta[^>]*name="description"[^>]*content="([^"]*)"'
    )
    assert "vocabulary trainer" in _attr(
        en, r'<meta[^>]*name="description"[^>]*content="([^"]*)"'
    ).lower()


def test_neznama_en_cesta_neskonci_chybou(client):
    r = client.get("/en/neexistuje", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/en"


def test_sitemap_obsahuje_obe_verzie(client):
    body = client.get("/sitemap.xml").text
    for sk_path in SK_PATHS:
        if sk_path == "/login":  # prihlásenie do sitemapy nedávame
            continue
        assert f"<loc>https://lexinova.fun{sk_path}</loc>" in body
        assert f"<loc>https://lexinova.fun{_en_path(sk_path)}</loc>" in body


# ── Samotný prepis HTML ──

def test_localize_neprepise_element_s_vnorenou_znackou():
    """Element s vnorenou značkou radšej necháme tak, než by sme mu zmazali obsah."""
    html = (
        '<html lang="en"><head><title>T</title></head><body>'
        '<p data-en="Plain" data-sk="Prostý">Plain</p>'
        '<p data-en="Rich" data-sk="Bohatý">Rich <b>bold</b></p>'
        "</body></html>"
    )
    out = localize(html, "sk", sk_url="https://x.sk/", en_url="https://x.sk/en")
    assert ">Prostý<" in out
    assert "Rich <b>bold</b>" in out


def test_localize_necha_len_jeden_jazykovy_blok():
    html = (
        '<html lang="sk"><head><title>T</title></head><body>'
        '<div id="content-sk"><h1>SK</h1><div>vnorene</div></div>'
        '<div id="content-en" style="display:none;"><h1>EN</h1></div>'
        "</body></html>"
    )
    sk = localize(html, "sk", sk_url="https://x.sk/", en_url="https://x.sk/en")
    assert "<h1>SK</h1>" in sk and "<h1>EN</h1>" not in sk
    assert "vnorene" in sk  # vnorený div nesmie useknúť blok predčasne

    en = localize(html, "en", sk_url="https://x.sk/", en_url="https://x.sk/en")
    assert "<h1>EN</h1>" in en and "<h1>SK</h1>" not in en
    assert 'style="display:none;"' not in en
