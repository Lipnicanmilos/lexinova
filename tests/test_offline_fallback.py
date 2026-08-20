# -*- coding: utf-8 -*-
"""Offline fallback service workera — komu sa smie ukázať cachovaná nástenka.

Fallback na `/dashboard` platil pre KAŽDÚ navigáciu, ktorej zlyhal fetch. Keď
prihlásenému používateľovi vypadla sieť nad `/` alebo `/pricing`, service worker
mu namiesto verejnej stránky vykreslil uloženú nástenku — navonok to vyzeralo,
že landing page presmerúva na dashboard. Testy sú statické nad zdrojom sw.js:
service worker sa v pytest nespustí, ale pravidlo sa dá prečítať z kódu.
"""
import re
from pathlib import Path

import pytest

SW = Path("app/static/sw.js").read_text(encoding="utf-8")


def _je_appkova(cesta: str) -> bool:
    """Prepis `isAppPage()` zo sw.js — obe strany musia dávať to isté."""
    nav = re.search(r"const NAV_PAGES_TO_CACHE = \[(.*?)\];", SW, re.S).group(1)
    prefixy = re.search(r"const APP_PATH_PREFIXES = \[(.*?)\];", SW, re.S).group(1)
    stranky = re.findall(r"'([^']+)'", nav)
    predpony = re.findall(r"'([^']+)'", prefixy)
    return cesta in stranky or cesta == "/hra" or any(cesta.startswith(p) for p in predpony)


def test_fallback_je_podmieneny():
    """Bez podmienky by sa nástenka vracala aj na verejných stránkach."""
    assert "if (isAppPage(url.pathname)) {" in SW
    telo = SW.split("if (isAppPage(url.pathname)) {", 1)[1]
    assert "caches.match('/dashboard')" in telo.split("}", 1)[0]
    # a nikde inde sa už nesmie objaviť
    assert SW.count("caches.match('/dashboard')") == 1


@pytest.mark.parametrize(
    "cesta", ["/dashboard", "/profile", "/test", "/repeat", "/classes", "/hra",
              "/category/5", "/admin"]
)
def test_appkove_cesty_dostanu_nastenku(cesta):
    assert _je_appkova(cesta), f"{cesta} má nárok na offline nástenku"


@pytest.mark.parametrize(
    "cesta", ["/", "/pricing", "/pre-ucitelov", "/demo", "/blog",
              "/blog/spaced-repetition", "/slovicka", "/slovicka/v-restauracii",
              "/register", "/login", "/s/ABC123", "/c/XYZ"]
)
def test_verejne_cesty_nastenku_nedostanu(cesta):
    """Vrátane `/s/` a `/c/` — to sú verejné landingy zdieľanej sady a triedy."""
    assert not _je_appkova(cesta), f"{cesta} je verejná, nástenka tam nepatrí"


def test_offline_stranka_ponuka_navrat_podla_typu_stranky():
    """Návštevníkovi bez účtu je odkaz na dashboard nanič."""
    assert "const backHref = isAppPage(url.pathname) ? '/dashboard' : '/';" in SW
    assert 'href="${backHref}"' in SW


def test_cache_name_sa_bumpol():
    """Zmena v sw.js bez bumpu `CACHE_NAME` sa k používateľom nedostane."""
    verzia = int(re.search(r"const CACHE_NAME = 'lexinova-v(\d+)';", SW).group(1))
    assert verzia >= 60
