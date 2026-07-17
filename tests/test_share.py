"""Zdieľanie sady kódom/linkom (Fáza 1 učiteľského kanála).

Pokrýva: generovanie/idempotenciu/zrušenie kódu, verejný náhľad, landing /s/,
import (kópia celej sady aj nad WORD_LIMIT_FREE, limit kategórií, sufix mena,
vlastná sada, cudzia kategória).
"""

from app.models.category import Category
from app.models.user import User
from app.models.word import Word
from app.services.limits import CATEGORY_LIMIT_FREE, WORD_LIMIT_FREE


def _register(client, email):
    res = client.post("/api/v1/register", json={"email": email, "password": "Abcdef12"})
    assert res.status_code == 200
    return res.json()["user"]


def _logout(client):
    client.post("/api/v1/logout")


def _create_category(client, name, user_id):
    res = client.post(
        "/api/v1/categories", json={"name": name, "description": "popis", "user_id": user_id}
    )
    assert res.status_code == 200
    return res.json()


def _seed_words(db_factory, user_id, category_id, n):
    db = db_factory()
    try:
        for i in range(n):
            db.add(Word(original_word=f"word{i}", translation=f"slovo{i}",
                        category_id=category_id, user_id=user_id,
                        language_from="en", language_to="sk"))
        db.commit()
    finally:
        db.close()


def _shared_setup(client, db_factory, owner_email, n_words=3, name="Zdielana"):
    """Vlastník: registrácia → kategória → slová → share kód. Vráti (kód, kategória)."""
    owner = _register(client, owner_email)
    cat = _create_category(client, name, owner["id"])
    _seed_words(db_factory, owner["id"], cat["id"], n_words)
    res = client.post(f"/api/v1/categories/{cat['id']}/share")
    assert res.status_code == 200
    return res.json()["share_code"], cat


# ── Generovanie a zrušenie kódu ──

def test_share_generates_code_and_url(client, db_factory):
    code, _ = _shared_setup(client, db_factory, "owner1@example.com")
    assert len(code) == 8


def test_share_is_idempotent(client, db_factory):
    code, cat = _shared_setup(client, db_factory, "owner2@example.com")
    res = client.post(f"/api/v1/categories/{cat['id']}/share")
    assert res.json()["share_code"] == code


def test_share_foreign_category_404(client, db_factory):
    _, cat = _shared_setup(client, db_factory, "owner3@example.com")
    _logout(client)
    _register(client, "cudzi3@example.com")
    assert client.post(f"/api/v1/categories/{cat['id']}/share").status_code == 404
    assert client.delete(f"/api/v1/categories/{cat['id']}/share").status_code == 404


def test_unshare_disables_link(client, db_factory):
    code, cat = _shared_setup(client, db_factory, "owner4@example.com")
    res = client.delete(f"/api/v1/categories/{cat['id']}/share")
    assert res.status_code == 200
    assert client.get(f"/api/v1/categories/shared/{code}").status_code == 404
    assert client.get(f"/s/{code}").status_code == 404


# ── Verejný náhľad ──

def test_preview_is_public(client, db_factory):
    code, _ = _shared_setup(client, db_factory, "owner5@example.com", n_words=4)
    _logout(client)

    res = client.get(f"/api/v1/categories/shared/{code}")
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Zdielana"
    assert data["total_words"] == 4
    assert data["language_from"] == "en"
    assert data["language_to"] == "sk"

    # Náhľad nesmie prezradiť vlastníka ani samotné slovíčka
    assert "user_id" not in data
    assert "words" not in data


def test_preview_code_is_case_insensitive(client, db_factory):
    code, _ = _shared_setup(client, db_factory, "owner6@example.com")
    assert client.get(f"/api/v1/categories/shared/{code.lower()}").status_code == 200


def test_preview_unknown_code_404(client):
    assert client.get("/api/v1/categories/shared/NEEXISTUJE").status_code == 404


# ── Landing stránka /s/{kód} ──

def test_share_landing_page(client, db_factory):
    code, _ = _shared_setup(client, db_factory, "owner7@example.com")
    _logout(client)
    res = client.get(f"/s/{code}")
    assert res.status_code == 200
    assert "Zdielana" in res.text
    # Neprihlásený vidí CTA s next parametrom späť na landing
    assert f"/login?next=/s/{code}" in res.text


def test_share_landing_page_logged_in(client, db_factory):
    code, _ = _shared_setup(client, db_factory, "owner8@example.com")
    _logout(client)
    _register(client, "student8@example.com")
    res = client.get(f"/s/{code}")
    assert res.status_code == 200
    assert "import-shared" in res.text  # prihlásený vidí import tlačidlo


def test_share_landing_unknown_code_404(client):
    res = client.get("/s/NEEXISTUJE")
    assert res.status_code == 404


# ── Import ──

def test_import_copies_whole_set_over_free_word_limit(client, db_factory):
    """Kópia príde celá aj nad WORD_LIMIT_FREE — limit platí pre vlastnú tvorbu."""
    n = WORD_LIMIT_FREE + 5
    code, _ = _shared_setup(client, db_factory, "owner9@example.com", n_words=n)
    _logout(client)
    student = _register(client, "student9@example.com")

    res = client.post("/api/v1/categories/import-shared", json={"share_code": code})
    assert res.status_code == 200
    data = res.json()
    assert data["imported_words"] == n
    assert data["category_name"] == "Zdielana"

    # Slová sú čerstvé kópie príjemcu (bez štatistík učenia vlastníka)
    db = db_factory()
    try:
        words = db.query(Word).filter(
            Word.category_id == data["category_id"], Word.user_id == student["id"]
        ).all()
        assert len(words) == n
        assert all((w.times_tested or 0) == 0 for w in words)
    finally:
        db.close()


def test_import_own_category_400(client, db_factory):
    code, _ = _shared_setup(client, db_factory, "owner10@example.com")
    res = client.post("/api/v1/categories/import-shared", json={"share_code": code})
    assert res.status_code == 400


def test_import_requires_auth(client, db_factory):
    code, _ = _shared_setup(client, db_factory, "owner11@example.com")
    _logout(client)
    res = client.post("/api/v1/categories/import-shared", json={"share_code": code})
    assert res.status_code == 401


def test_import_counts_into_category_limit(client, db_factory):
    """Free príjemca s plným limitom kategórií import nespraví (400)."""
    code, _ = _shared_setup(client, db_factory, "owner12@example.com")
    _logout(client)
    student = _register(client, "student12@example.com")
    for i in range(CATEGORY_LIMIT_FREE):
        _create_category(client, f"Moja {i}", student["id"])

    res = client.post("/api/v1/categories/import-shared", json={"share_code": code})
    assert res.status_code == 400
    assert str(CATEGORY_LIMIT_FREE) in res.json()["detail"]


def test_import_duplicate_name_gets_suffix(client, db_factory):
    code, _ = _shared_setup(client, db_factory, "owner13@example.com")
    _logout(client)
    student = _register(client, "student13@example.com")
    _create_category(client, "Zdielana", student["id"])  # meno už existuje

    res = client.post("/api/v1/categories/import-shared", json={"share_code": code})
    assert res.status_code == 200
    assert res.json()["category_name"] == "Zdielana (2)"


def test_import_unknown_code_404(client):
    _register(client, "student14@example.com")
    res = client.post("/api/v1/categories/import-shared", json={"share_code": "NEEXISTUJE"})
    assert res.status_code == 404


def test_categories_list_exposes_share_code_to_owner(client, db_factory):
    code, cat = _shared_setup(client, db_factory, "owner15@example.com")
    data = client.get("/api/v1/categories").json()
    mine = next(c for c in data if c["id"] == cat["id"])
    assert mine["share_code"] == code
