# -*- coding: utf-8 -*-
"""Resource hints v <head> — poradie, v akom sa začnú sťahovať fonty.

Bez `preload` je reťaz HTML → fonts.css → woff2, teda dva sériové round-tripy
predtým, než sa text vykreslí finálnym fontom. Testy strážia, že hinty sú na
stránke, že sú PRED `fonts.css` (za ním by už nič neurýchlili) a že na ne
nezabudne nová šablóna.
"""
import re
from pathlib import Path

import pytest

FONTY = [
    "/static/fonts/inter-latin.woff2",
    "/static/fonts/inter-latin-ext.woff2",
    "/static/fonts/space-grotesk-latin.woff2",
    "/static/fonts/space-grotesk-latin-ext.woff2",
]

STRANKY = ["/", "/en", "/pricing", "/demo", "/pre-ucitelov", "/blog", "/slovicka",
           "/slovicka/v-restauracii", "/register", "/login"]


@pytest.mark.parametrize("path", STRANKY)
def test_fonty_su_preloadovane(client, path):
    html = client.get(path).text
    for font in FONTY:
        assert f'rel="preload" as="font" type="font/woff2" crossorigin href="{font}"' in html, (
            f"{path}: chýba preload pre {font}"
        )


@pytest.mark.parametrize("path", STRANKY)
def test_preload_je_pred_fonts_css(client, path):
    """Za `fonts.css` by preload prišiel neskoro — prehliadač ho už objaví sám."""
    html = client.get(path).text
    prvy_preload = html.index('rel="preload" as="font"')
    fonts_css = html.index("/static/css/fonts.css")
    assert prvy_preload < fonts_css, f"{path}: preload je až za fonts.css"


def test_crossorigin_je_pri_kazdom_preloade(client):
    """Bez `crossorigin` prehliadač preload zahodí a font stiahne druhýkrát.

    Fonty sa sťahujú v CORS režime aj z vlastnej domény, takže preload bez
    tohto atribútu nesedí s neskorším requestom z CSS a je zadarmo navyše.
    """
    html = client.get("/").text
    for tag in re.findall(r'<link[^>]+rel="preload"[^>]*>', html):
        assert 'as="font"' in tag and "crossorigin" in tag, tag


def test_preconnect_len_ked_bezi_analytika(client):
    """S vypnutou analytikou (lokál, testy) nemá na čo otvárať spojenie."""
    assert "preconnect" not in client.get("/").text


def test_preconnect_miery_na_origin_analytiky():
    from app.services.runtime import templates

    sablona = templates.env.get_template("partials/head_hints.html")
    html = sablona.render(analytics_origin="https://plausible.io")
    assert '<link rel="preconnect" href="https://plausible.io" crossorigin>' in html


def test_kazda_sablona_s_fontami_ma_aj_hinty():
    """Nová stránka nesmie hinty potichu vynechať."""
    chyba = []
    for f in sorted(Path("app/templates").rglob("*.html")):
        text = f.read_text(encoding="utf-8")
        if "/static/css/fonts.css" not in text:
            continue
        if 'partials/head_hints.html' not in text:
            chyba.append(str(f))
    assert not chyba, f"šablóny bez head_hints: {chyba}"
