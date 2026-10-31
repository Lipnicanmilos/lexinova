"""Spôsoby precvičovania na stránke sady.

Dlaždíc bolo päť a zoznam slov začínal na telefóne až na ~1003 px. Teraz má
stránka jednu hlavnú akciu (Učiť sa) a dve vedľajšie; zvyšok je zbalený v
`<details>`, takže zbalenie je v HTML a stránka sa po načítaní nepohne.
"""
from app.models.user import User


def _set_page(client, db_factory, email="modes@example.com"):
    client.post("/api/v1/register", json={"email": email, "password": "Abcdef12"})
    client.post("/api/v1/login", json={"email": email, "password": "Abcdef12"})
    db = db_factory()
    try:
        user_id = db.query(User).filter(User.email == email).one().id
    finally:
        db.close()
    category_id = client.post(
        "/api/v1/categories", json={"name": "Spôsoby", "description": "", "user_id": user_id}
    ).json()["id"]
    return client.get(f"/category/{category_id}/words").text


def test_main_actions_stay_outside_the_collapsed_group(client, db_factory):
    page = _set_page(client, db_factory)

    collapsed = page.index('<details class="more-modes">')
    for label in ('data-sk="Učiť sa"', 'data-sk="Počúvať"', 'data-sk="S Lexi"'):
        assert page.index(label) < collapsed, label


def test_other_ways_to_practise_are_collapsed_but_still_there(client, db_factory):
    page = _set_page(client, db_factory, "modes2@example.com")

    start = page.index('<details class="more-modes">')
    group = page[start:page.index('</details>', start)]
    for label in ("Kartičky", "Počúvanie", "Dopĺňanie do viet", "Osemsmerovka"):
        assert f'data-sk="{label}"' in group, label
    assert "<details class=\"more-modes\" open" not in page


def test_word_list_follows_right_after_the_set_head(client, db_factory):
    page = _set_page(client, db_factory, "modes3@example.com")

    assert page.index('class="set-head"') < page.index('id="wordsList"')
    # Medzi hlavičkou a zoznamom nie je nič, čo by bolo stále rozbalené.
    between = page[page.index('class="words-section"'):page.index('id="wordsList"')]
    assert "<details" in between and " open" not in between.split('id="listOptions"')[1]


def test_empty_set_hides_learning_until_it_has_words(client, db_factory):
    page = _set_page(client, db_factory, "modes4@example.com")
    assert 'id="setLearn" style="display:none;"' in page

    script = client.get("/static/js/page-category_words.js").text
    assert "getElementById('setLearn').style.display = total ? '' : 'none'" in script
