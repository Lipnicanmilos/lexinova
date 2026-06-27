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
