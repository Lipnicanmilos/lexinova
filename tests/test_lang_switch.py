# -*- coding: utf-8 -*-
"""Prepínač SK/EN na stránkach s dvoma jazykovými blokmi v šablóne.

`localize()` neaktívny blok zo servírovaného HTML odstráni, ale `setLang()`
v šablóne na oba bloky slepo siahala — `TypeError` padol hneď pri načítaní
a funkcia nedobehla ani po riadok, ktorý zvýrazňuje aktívny jazyk. Navigáciu
to nerozbilo (tú rieši listener vložený do <head>), ale ani jedno z tlačidiel
SK/EN nebolo označené ako aktívne.
"""
import re
from pathlib import Path

import pytest

# (SK cesta, EN cesta) — stránky, ktoré majú v šablóne `content-sk`/`content-en`.
DVOJICE = [
    ("/pricing", "/en/pricing"),
    ("/pre-ucitelov", "/en/pre-ucitelov"),
    ("/privacy", "/en/privacy"),
    ("/terms", "/en/terms"),
    ("/refunds", "/en/refunds"),
]

SABLONY = ["pricing", "for_teachers", "privacy", "terms", "refunds"]


@pytest.mark.parametrize("sk,en", DVOJICE)
def test_servirovany_je_prave_jeden_jazykovy_blok(client, sk, en):
    """Toto je predpoklad, na ktorom celá oprava stojí."""
    for cesta, ma, nema in ((sk, "content-sk", "content-en"), (en, "content-en", "content-sk")):
        html = client.get(cesta).text
        assert f'id="{ma}"' in html, f"{cesta}: chýba {ma}"
        assert f'id="{nema}"' not in html, f"{cesta}: {nema} tam nemá čo robiť"


@pytest.mark.parametrize("nazov", SABLONY)
def test_setlang_nesiaha_na_blok_bez_kontroly(nazov):
    """Slepý `.style` na odstránenom bloku bola presne tá pôvodná chyba."""
    zdroj = Path(f"app/templates/{nazov}.html").read_text(encoding="utf-8")
    assert not re.search(r"getElementById\('content-(sk|en)'\)\s*\.", zdroj), (
        f"{nazov}: `getElementById('content-*')` bez kontroly na null"
    )


@pytest.mark.parametrize("nazov", SABLONY)
def test_sablona_neprepisuje_titulok_natvrdo(nazov):
    """Titulok posiela server; natvrdo napísaný v JS sa rozíde s ním.

    Na `/pricing` a `/pre-ucitelov` sa už raz rozišiel — v `setLang` ostali
    staré krátke titulky spred úpravy pre vyhľadávače.
    """
    zdroj = Path(f"app/templates/{nazov}.html").read_text(encoding="utf-8")
    assert "document.title = l ===" not in zdroj, f"{nazov}: natvrdo napísaný titulok"


@pytest.mark.parametrize("sk,en", DVOJICE)
def test_prepinac_vie_o_oboch_adresach(client, sk, en):
    """Listener v <head> musí poznať obe cesty, inak prepnutie nikam nevedie."""
    html = client.get(sk).text
    assert "__serverLang" in html and "stopImmediatePropagation" in html
    prepinac = re.search(r"var u=\{sk:\"([^\"]+)\",en:\"([^\"]+)\"\}", html)
    assert prepinac, f"{sk}: prepínač nemá adresy"
    assert prepinac.group(1) == sk
    assert prepinac.group(2) == en


@pytest.mark.parametrize("sk,en", DVOJICE)
def test_obe_verzie_existuju_a_maju_spravny_lang(client, sk, en):
    assert 'lang="sk"' in client.get(sk).text
    odpoved = client.get(en)
    assert odpoved.status_code == 200, f"{en} nevracia 200"
    assert 'lang="en"' in odpoved.text


@pytest.mark.parametrize("sk,en", DVOJICE)
def test_tlacidla_prepinaca_su_na_stranke(client, sk, en):
    """Bez `data-lang` by injektovaný listener nemal čo zachytiť."""
    for cesta in (sk, en):
        html = client.get(cesta).text
        assert 'data-lang="sk"' in html and 'data-lang="en"' in html, cesta


@pytest.mark.parametrize("nazov", SABLONY)
def test_jazyk_sa_berie_z_url_nie_z_localstorage(nazov):
    """`preferredLang` nesmie prebiť jazyk, ktorý poslal server.

    Toto bola regresia z prvého pokusu o opravu: `privacy`, `terms` a
    `refunds` čítali len `localStorage`. Kým `setLang()` padala na chýbajúcom
    bloku, nebolo to vidieť — po jej opravení začala uložená voľba `en`
    prepisovať servírovanú slovenskú stránku na anglickú, v rozpore
    s `<html lang="sk">` aj s canonicalom.
    """
    zdroj = Path(f"app/templates/{nazov}.html").read_text(encoding="utf-8")
    init = re.search(r"let lang = ([^;]+);", zdroj)
    assert init, f"{nazov}: nenašiel som inicializáciu `lang`"
    assert "window.__serverLang" in init.group(1), (
        f"{nazov}: jazyk sa berie z localStorage, nie z URL — {init.group(1)}"
    )


@pytest.mark.parametrize("sk,en", DVOJICE)
def test_server_posiela_jazyk_do_javascriptu(client, sk, en):
    for cesta, ocakavany in ((sk, "sk"), (en, "en")):
        html = client.get(cesta).text
        assert f'window.__serverLang="{ocakavany}"' in html, cesta
