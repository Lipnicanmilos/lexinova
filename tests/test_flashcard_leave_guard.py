"""Odchod z bežiaceho testu kartičiek (tlačidlo späť, zavretá karta).

Regresia: stránka `/test` riešila odchod len cez odkaz „← Dashboard" — tlačidlo
späť (v prehliadači aj hardvérové na mobile) odišlo ticho a odpovede sa stratili.
Správanie je čisto klientske (overené naživo v prehliadači), tu strážime aspoň to,
že sa poistky nestratia pri budúcich úpravách.

Skripty stránok sú od 2026-08-19 v `/static/js/page-*.js` (inline verzia sa
nedala cachovať), takže sa kontroluje obsah tých súborov — nie HTML.
"""


def _login(client, email="test-leave@example.com"):
    res = client.post("/api/v1/register", json={"email": email, "password": "Abcdef12"})
    assert res.status_code == 200


def _page_script(client, name):
    """Stránka sa musí načítať aj s odkazom na svoj skript; vráti obsah skriptu."""
    res = client.get(f"/static/js/page-{name}.js")
    assert res.status_code == 200, f"page-{name}.js sa nenačítal"
    return res.text


def test_stranka_testu_striezi_odchod_spat(client):
    _login(client)

    page = client.get("/test").text
    assert "/static/js/page-flashcard_test.js" in page, "stránka nelinkuje svoj skript"

    script = _page_script(client, "flashcard_test")
    assert "popstate" in script          # tlačidlo späť → potvrdzovací modál
    assert "armHistoryGuard" in script   # strážna položka v histórii
    assert "beforeunload" in script      # zavretá karta / reload / iná adresa


def test_stranka_testu_uklada_odpovede_pri_zaniku_stranky(client):
    _login(client, "test-leave2@example.com")

    script = _page_script(client, "flashcard_test")

    assert "sendBeacon" in script        # poistné uloženie, keď stránka zaniká
    assert "answers.slice(pendingFrom)" in script  # bez toho by sa karty počítali dvakrát


def test_stranka_sady_obnovi_data_po_navrate_spat(client):
    """Späť z testu vracia stránku z bfcache — DOMContentLoaded už nebeží.

    Bez obnovy na `pageshow` by percentá „Viem/Neviem" aj úrovne slovíčok ostali
    v stave spred testu (dashboard má na `pageshow` rovno celý init).
    """
    _login(client, "test-leave3@example.com")
    cat = client.post(
        "/api/v1/categories", json={"name": "Sada", "description": "popis", "user_id": 1}
    )
    assert cat.status_code == 200

    page = client.get(f"/category/{cat.json()['id']}/words").text
    assert "/static/js/page-category_words.js" in page

    script = _page_script(client, "category_words")
    assert "pageshow" in script
    assert "e.persisted" in script
