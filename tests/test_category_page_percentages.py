"""Percentá „Neviem / Viem" v hlavičke stránky kategórie.

Regresia: šablóna vypisovala hodnoty z databázy na jedno desatinné miesto
(„44.4%", pri prázdnej úrovni „0.0%"), kým skript stránky ich po dobehnutí API
prepísal na celé čísla („44%"). Text tak sekundu-dve po načítaní zmenil šírku
a tlačidlá poskočili. Server aj skript musia dať ten istý text.

Percentá sú v legende pod pruhom; tlačidlá spôsobov precvičovania majú stály
popisok bez čísla.
"""


def _login(client, email):
    res = client.post("/api/v1/register", json={"email": email, "password": "Abcdef12"})
    assert res.status_code == 200


def _category(client, name="Sada"):
    res = client.post(
        "/api/v1/categories", json={"name": name, "description": "", "user_id": 1}
    )
    assert res.status_code == 200
    return res.json()["id"]


def _add_words(client, category_id, total, known):
    for i in range(total):
        res = client.post(
            "/api/v1/words",
            json={"original_word": f"word{i}", "translation": f"slovo{i}", "category_id": category_id},
        )
        assert res.status_code == 200
        if i < known:
            res = client.put(
                f"/api/v1/words/{res.json()['id']}/knowledge-level",
                json={"knowledge_level": "know"},
            )
            assert res.status_code == 200


def test_percenta_su_cele_cisla_a_davaju_sto(client):
    _login(client, "pct1@example.com")
    category_id = _category(client)
    _add_words(client, category_id, total=9, known=5)  # 55,6 % / 44,4 %

    page = client.get(f"/category/{category_id}/words").text

    assert 'id="setDontKnowPct">(44%)<' in page
    assert 'id="setKnowPct">(56%)<' in page
    assert "44.4" not in page and "55.6" not in page
    # Tlačidlá nesú stály text — číslo v nich menilo šírku a rozbíjalo riadok.
    assert "Neviem (44%)" not in page


def test_polovica_sa_zaokruhluje_nahor_ako_v_js(client):
    """12,5 % → 13 ako Math.round; Pythonov round() by dal 12."""
    _login(client, "pct2@example.com")
    category_id = _category(client)
    _add_words(client, category_id, total=8, known=1)

    page = client.get(f"/category/{category_id}/words").text

    assert 'id="setKnowPct">(13%)<' in page
    assert 'id="setDontKnowPct">(87%)<' in page


def test_prazdna_kategoria_ma_nuly_bez_desatin(client):
    _login(client, "pct3@example.com")
    category_id = _category(client)

    page = client.get(f"/category/{category_id}/words").text

    assert 'id="setDontKnowPct">(0%)<' in page
    assert 'id="setKnowPct">(0%)<' in page
    assert "0.0%" not in page


def test_skript_pocita_percenta_rovnako_ako_server(client):
    script = client.get("/static/js/page-category_words.js").text

    assert "function testButtonPercents" in script
    assert "100 - know" in script
