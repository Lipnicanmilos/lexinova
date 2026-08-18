"""SEO základy verejných stránok — bez nich Google pracuje s domnienkami.

Kontroluje to, čo audit našiel ako chýbajúce: popis pre výsledky vyhľadávania,
náhľad pri zdieľaní, práve jeden H1, odkazy v HTML (nie až po spustení JS)
a čistú sitemapu.
"""
import json
import re

import pytest

# Verejné, indexovateľné stránky. Appka (dashboard, kartičky) je v robots.txt
# zakázaná, tam tieto pravidlá nedávajú zmysel.
PUBLIC_PAGES = [
    "/",
    "/pricing",
    "/demo",
    "/register",
    "/login",
    "/blog",
    "/slovicka",
    "/slovicka/v-restauracii",
]


@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_stranka_ma_popis_a_canonical(client, path):
    html = client.get(path).text
    desc = re.search(
        r'<meta[^>]+name="description"[^>]+content="([^"]*)"', html, re.I
    )
    assert desc, f"{path}: chýba meta description"
    # Príliš krátky popis si Google prepíše vlastným výberom textu.
    assert len(desc.group(1)) >= 60, f"{path}: meta description je príliš krátky"
    assert re.search(r'<link[^>]+rel="canonical"', html, re.I), f"{path}: chýba canonical"


@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_stranka_ma_nahlad_pri_zdielani(client, path):
    html = client.get(path).text
    for tag in ('property="og:title"', 'property="og:image"', 'name="twitter:card"'):
        assert tag in html, f"{path}: chýba {tag}"


@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_stranka_ma_prave_jeden_h1(client, path):
    html = client.get(path).text
    assert len(re.findall(r"<h1[\s>]", html, re.I)) == 1, f"{path}: musí byť práve jeden H1"


@pytest.mark.parametrize("path", ["/", "/blog", "/slovicka"])
def test_odkazy_su_v_html_bez_javascriptu(client, path):
    """Pätičku vykresľuje JS — odkazy na obsahové stránky musia byť aj v HTML."""
    html = client.get(path).text
    assert 'href="/slovicka"' in html, f"{path}: chýba odkaz na tematické stránky"
    assert 'href="/blog"' in html, f"{path}: chýba odkaz na blog"


def test_sitemap_neponuka_prihlasenie(client):
    body = client.get("/sitemap.xml").text
    assert "<loc>" in body
    assert "/login" not in body


def test_strukturovane_data_su_platny_json(client):
    for path in ["/", "/pricing", "/slovicka", "/slovicka/v-restauracii"]:
        html = client.get(path).text
        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', html, re.S
        )
        assert blocks, f"{path}: chýbajú štruktúrované dáta"
        for block in blocks:
            json.loads(block)  # neplatný JSON = Google blok zahodí


def test_cennik_ma_faq_pre_google(client):
    """FAQ na stránke musí sedieť s tým, čo hlásime Googlu — inak ho zahodí."""
    html = client.get("/pricing").text
    block = re.search(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S
    ).group(1)
    data = json.loads(block)
    assert data["@type"] == "FAQPage"
    for item in data["mainEntity"]:
        assert item["name"] in html
        assert item["acceptedAnswer"]["text"] in html
