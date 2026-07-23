"""Verejné stránky, security hlavičky a self-hostované fonty."""
import pytest

PUBLIC_PAGES = ["/", "/login", "/register", "/demo", "/privacy", "/terms", "/forgot-password"]


@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_public_page_loads(client, path):
    assert client.get(path).status_code == 200


def test_security_headers_present(client):
    r = client.get("/login")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" in r.headers
    assert "Referrer-Policy" in r.headers


def test_security_headers_on_404(client):
    r = client.get("/this-page-does-not-exist")
    assert r.status_code == 404
    assert "Content-Security-Policy" in r.headers


def test_fonts_are_self_hosted(client):
    page = client.get("/login")
    assert "/static/css/fonts.css" in page.text
    assert "fonts.googleapis" not in page.text  # žiadny Google CDN
    assert client.get("/static/css/fonts.css").status_code == 200
    assert client.get("/static/fonts/inter-latin.woff2").status_code == 200


def test_privacy_and_terms_bilingual(client):
    for path in ("/privacy", "/terms"):
        text = client.get(path).text
        assert 'id="content-sk"' in text
        assert 'id="content-en"' in text


# Stránky zo sitemap.xml — bez canonical si Google vyberá kánonickú adresu sám
# a hlási „Duplikovať bez kánonickej adresy vybranej používateľom".
SITEMAP_PAGES = [
    ("/", "https://lexinova.fun/"),
    ("/pricing", "https://lexinova.fun/pricing"),
    ("/demo", "https://lexinova.fun/demo"),
    ("/register", "https://lexinova.fun/register"),
    ("/login", "https://lexinova.fun/login"),
    ("/terms", "https://lexinova.fun/terms"),
    ("/privacy", "https://lexinova.fun/privacy"),
    ("/refunds", "https://lexinova.fun/refunds"),
    ("/blog", "https://lexinova.fun/blog"),
]


@pytest.mark.parametrize("path,canonical", SITEMAP_PAGES)
def test_verejne_stranky_maju_canonical(client, path, canonical):
    assert f'<link rel="canonical" href="{canonical}">' in client.get(path).text


def test_www_presmeruje_na_apex(client):
    """www aj apex ukazujú na to isté Cloud Run — bez 301 beží web na dvoch adresách."""
    r = client.get("/pricing", headers={"host": "www.lexinova.fun"}, follow_redirects=False)

    assert r.status_code == 301
    assert r.headers["location"].endswith("://lexinova.fun/pricing")


def test_www_presmerovanie_zachova_query(client):
    r = client.get(
        "/login", params={"next": "/s/ABC123"},
        headers={"host": "www.lexinova.fun"}, follow_redirects=False,
    )

    assert r.status_code == 301
    assert r.headers["location"].endswith("://lexinova.fun/login?next=%2Fs%2FABC123")


def test_auth_na_www_sa_nepresmeruje(client):
    """OAuth state cookie je viazaná na host — presmerovanie callbacku by login zhodilo."""
    r = client.get(
        "/auth/finalize", params={"t": "invalid"},
        headers={"host": "www.lexinova.fun"}, follow_redirects=False,
    )

    assert r.status_code != 301
