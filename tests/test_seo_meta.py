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


@pytest.mark.parametrize("path,lang", [("/pricing", "sk"), ("/en/pricing", "en")])
def test_cennik_ma_faq_pre_google(client, path, lang):
    """FAQ musí sedieť s viditeľným textom — aj jazykom.

    Slovenský FAQ markup na anglickej stránke Google zahodí, preto je JSON-LD
    vnútri jazykového bloku a s URL sa mení aj on.
    """
    html = client.get(path).text
    bloky = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert len(bloky) == 1, f"{path}: na stránke má byť práve jeden FAQ blok"
    data = json.loads(bloky[0])
    assert data["@type"] == "FAQPage"
    assert data["inLanguage"] == lang
    telo = html.split('id="content-', 1)[1]
    for item in data["mainEntity"]:
        assert item["name"] in telo, f'{path}: otázka nie je v texte — {item["name"]}'
        assert item["acceptedAnswer"]["text"] in telo
