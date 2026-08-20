"""Stránka pre učiteľov — vstupná brána pre kanál, ktorý privádza celé triedy.

Landing o triedach nepísal nič, hoci je to funkcia, ktorou sa LexiNova odlišuje
na slovenskom trhu. Testy strážia, že stránka existuje v oboch jazykoch, že sa
na ňu dá dostať z hlavnej stránky a že sľubuje presne to, čo appka vie.
"""
import re


def test_page_exists_in_both_languages(client):
    sk = client.get("/pre-ucitelov")
    en = client.get("/en/pre-ucitelov")

    assert sk.status_code == 200
    assert en.status_code == 200
    assert 'lang="sk"' in sk.text
    assert 'lang="en"' in en.text


def test_page_has_canonical_and_hreflang(client):
    html = client.get("/pre-ucitelov").text

    assert '<link rel="canonical" href="https://lexinova.fun/pre-ucitelov">' in html
    assert 'hreflang="sk"' in html and 'hreflang="en"' in html
    assert 'hreflang="x-default"' in html


def test_page_has_exactly_one_h1(client):
    """Dva H1 (SK aj EN blok naraz) by Googlu riedili tému stránky."""
    for url in ("/pre-ucitelov", "/en/pre-ucitelov"):
        html = client.get(url).text
        assert len(re.findall(r"<h1\b", html)) == 1, url


def test_landing_links_to_teachers_page(client):
    html = client.get("/").text
    assert '/pre-ucitelov' in html, "z hlavnej stránky sa na ňu nedá dostať"


def test_page_is_in_sitemap(client):
    assert "https://lexinova.fun/pre-ucitelov" in client.get("/sitemap.xml").text


def test_promise_matches_what_the_app_does(client):
    """Prvá trieda je zadarmo — text to tvrdí, kód to musí dovoliť."""
    from app.routers.classes import CLASS_LIMIT_FREE

    assert CLASS_LIMIT_FREE == 1
    html = client.get("/pre-ucitelov").text
    assert "Prvá trieda je zadarmo" in html
