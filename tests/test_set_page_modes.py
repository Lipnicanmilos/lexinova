"""Spôsoby precvičovania na stránke sady — na úzkom displeji zbalené.

Dlaždíc je päť a pod sebou tlačili zoznam slov na telefóne až na ~1414 px.
Viditeľné ostávajú Kartičky, ostatné sa rozbalia tlačidlom. Zbalenie musí byť
v CSS (nie až v skripte), inak by sa stránka po načítaní pohla.
"""
import re

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


def test_only_flashcards_stay_outside_the_collapsed_group(client, db_factory):
    page = _set_page(client, db_factory)

    tiles = re.findall(r'<div class="(mode-tile[^"]*)">\s*<div class="mode-head">.*?data-sk="([^"]+)"',
                       page, re.S)
    assert [(title, "extra" in classes.split()) for classes, title in tiles] == [
        ("Kartičky", False),
        ("Počúvanie", True),
        ("Osemsmerovka", True),
        ("Dopĺňanie do viet", True),
        ("Rozhovor s AI", True),
    ]
    # Prepínač je hneď za Kartičkami a čítačke obrazovky hovorí, čo ovláda.
    toggle = page.index('id="modesToggle"')
    assert page.index('data-sk="Kartičky"') < toggle < page.index('data-sk="Počúvanie"')
    assert 'aria-expanded="false" aria-controls="setModes"' in page


def test_collapsing_is_done_in_css_and_only_on_narrow_screens(client):
    css = client.get("/static/css/page-category_words.css").text
    narrow = css[css.index("@media (max-width: 900px)"):]
    narrow = narrow[:narrow.index("@media", 1)]

    assert ".set-modes:not(.expanded) .mode-tile.extra { display: none; }" in narrow
    # Mimo media query je prepínač skrytý a dlaždice sa neskrývajú nikde.
    wide = css[:css.index("@media (max-width: 900px)")]
    assert ".modes-toggle { display: none; }" in wide
    assert ".mode-tile.extra" not in wide

    script = client.get("/static/js/page-category_words.js").text
    assert "classList.toggle('expanded')" in script
