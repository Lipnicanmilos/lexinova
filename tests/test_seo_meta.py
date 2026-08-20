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


# ── Výpis blogu: štruktúrované dáta ──────────────────────────────────────
# Jednotlivé články `Article` schému mali, samotný výpis žiadnu — Google tak
# nemal z čoho postaviť rich result pre /blog.

@pytest.mark.parametrize("path,lang", [("/blog", "sk"), ("/blog/en", "en")])
def test_vypis_blogu_ma_strukturovane_data(client, path, lang):
    html = client.get(path).text
    bloky = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert len(bloky) == 1, f"{path}: očakávam práve jeden JSON-LD blok"

    graf = json.loads(bloky[0])["@graph"]
    typy = {uzol["@type"] for uzol in graf}
    assert {"Blog", "ItemList", "BreadcrumbList"} <= typy, f"{path}: chýba {typy}"

    blog = next(u for u in graf if u["@type"] == "Blog")
    assert blog["inLanguage"] == lang
    assert blog["url"].endswith(path)


@pytest.mark.parametrize("path", ["/blog", "/blog/en"])
def test_zoznam_v_json_ld_sedi_s_vypisom(client, path):
    """Počet aj URL musia sedieť s tým, čo je na stránke — inak je to klam."""
    html = client.get(path).text
    graf = json.loads(
        re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)[0]
    )["@graph"]

    zoznam = next(u for u in graf if u["@type"] == "ItemList")
    blog = next(u for u in graf if u["@type"] == "Blog")
    assert zoznam["numberOfItems"] == len(zoznam["itemListElement"]) == len(blog["blogPost"])

    for polozka in zoznam["itemListElement"]:
        cesta = polozka["url"].replace("https://lexinova.fun", "")
        assert f'href="{cesta}"' in html, f"{path}: {cesta} nie je vo výpise"
        assert client.get(cesta).status_code == 200


def test_breadcrumb_blogu_vedie_domov(client):
    graf = json.loads(
        re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            client.get("/blog").text,
            re.S,
        )[0]
    )["@graph"]
    drobky = next(u for u in graf if u["@type"] == "BreadcrumbList")["itemListElement"]
    assert [d["position"] for d in drobky] == [1, 2]
    assert drobky[-1]["item"].endswith("/blog")


# ── Dĺžky titulkov a popisov ─────────────────────────────────────────────
# Google odreže titulok po ~60 znakoch a príliš krátky popis si prepíše
# vlastným výberom textu. Stráženie sa týka stránok, ktoré predávajú.

PREDAJNE_STRANKY = ["/pricing", "/en/pricing", "/pre-ucitelov", "/en/pre-ucitelov"]


@pytest.mark.parametrize("path", PREDAJNE_STRANKY)
def test_titulok_vyuziva_priestor_a_nepretecie(client, path):
    html = client.get(path).text
    titulok = re.search(r"<title[^>]*>(.*?)</title>", html, re.S).group(1).strip()
    assert 40 <= len(titulok) <= 60, f"{path}: titulok má {len(titulok)} znakov — {titulok}"
    assert "LexiNova" in titulok


@pytest.mark.parametrize("path", PREDAJNE_STRANKY)
def test_popis_vyuziva_priestor(client, path):
    html = client.get(path).text
    popis = re.search(
        r'<meta[^>]+name="description"[^>]+content="([^"]*)"', html, re.I
    ).group(1)
    assert 120 <= len(popis) <= 160, f"{path}: popis má {len(popis)} znakov"


def test_cena_v_titulku_sedi_s_cenou_na_stranke(client):
    """Titulok sľubuje sumu — musí byť tá, ktorú návštevník na stránke uvidí."""
    html = client.get("/pricing").text
    titulok = re.search(r"<title[^>]*>(.*?)</title>", html, re.S).group(1)
    assert "4,99" in titulok
    assert 'data-price-monthly="€4,99"' in html
