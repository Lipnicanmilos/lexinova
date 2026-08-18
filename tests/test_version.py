"""Verzia appky — v pätičke a na /api/version.

Build číslo prepisuje git hook (`.githooks/pre-commit`) pri každom commite, takže
z bežiacej stránky je vidno, ktorý commit je nasadený.
"""
import re

from app.services.runtime import APP_VERSION
from app.version import BUILD, MAJOR_MINOR, VERSION


def test_format_verzie():
    assert re.fullmatch(r"\d+\.\d+\.\d+", VERSION), VERSION
    assert VERSION == f"{MAJOR_MINOR}.{BUILD}"


def test_endpoint_vracia_verziu(client):
    r = client.get("/api/version")
    assert r.status_code == 200
    assert r.json() == {"version": APP_VERSION}


def test_stranky_nesu_verziu_pre_paticku(client):
    """site-footer.js ju číta z meta tagu — bez neho by pätička verziu neukázala."""
    for path in ("/", "/dashboard", "/slovicka", "/blog"):
        html = client.get(path, follow_redirects=True).text
        assert f'<meta name="app-version" content="{APP_VERSION}">' in html, path
