"""Odchod z bežiaceho testu kartičiek (tlačidlo späť, zavretá karta).

Regresia: stránka `/test` riešila odchod len cez odkaz „← Dashboard" — tlačidlo
späť (v prehliadači aj hardvérové na mobile) odišlo ticho a odpovede sa stratili.
Správanie je čisto klientske (overené naživo v prehliadači), tu strážime aspoň to,
že sa poistky zo šablóny nestratia pri budúcich úpravách.
"""


def _login(client, email="test-leave@example.com"):
    res = client.post("/api/v1/register", json={"email": email, "password": "Abcdef12"})
    assert res.status_code == 200


def test_stranka_testu_striezi_odchod_spat(client):
    _login(client)

    page = client.get("/test").text

    assert "popstate" in page          # tlačidlo späť → potvrdzovací modál
    assert "armHistoryGuard" in page   # strážna položka v histórii
    assert "beforeunload" in page      # zavretá karta / reload / iná adresa


def test_stranka_testu_uklada_odpovede_pri_zaniku_stranky(client):
    _login(client, "test-leave2@example.com")

    page = client.get("/test").text

    assert "sendBeacon" in page        # poistné uloženie, keď stránka zaniká
    assert "answers.slice(pendingFrom)" in page  # bez toho by sa karty počítali dvakrát


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

    assert "pageshow" in page
    assert "e.persisted" in page
