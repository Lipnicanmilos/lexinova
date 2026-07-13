"""Import slovíčok z Excelu — poškodený súbor musí vrátiť 400, nie 500.

500-ka sa loguje ako ERROR → falošný e-mail alert pri každom pokazenom súbore
od používateľa (nájdené E2E behom 2026-07-10, opravené 2026-07-13).
"""
import io

import pandas as pd

from app.models.user import User


def _register(client, email):
    client.post("/api/v1/register", json={"email": email, "password": "Abcdef12"})


def _create_category(client, db_factory, email, name="Import test"):
    db = db_factory()
    try:
        user_id = db.query(User).filter(User.email == email).first().id
    finally:
        db.close()
    res = client.post(
        "/api/v1/categories", json={"name": name, "description": "", "user_id": user_id}
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _upload(client, category_id, content: bytes, filename="words.xlsx"):
    return client.post(
        "/api/v1/words/import",
        files={"excelFile": (filename, io.BytesIO(content), "application/vnd.ms-excel")},
        data={"category_id": str(category_id)},
    )


def test_import_corrupt_xlsx_returns_400_not_500(client, db_factory):
    """Nečitateľný obsah s príponou .xlsx → 400 so zrozumiteľnou hláškou."""
    _register(client, "import_bad@example.com")
    cat_id = _create_category(client, db_factory, "import_bad@example.com")

    res = _upload(client, cat_id, b"toto nie je excel, len rozbity subor")
    assert res.status_code == 400, res.text
    assert "neda" in res.json()["detail"].lower() or "nedá" in res.json()["detail"]


def test_import_valid_xlsx_inserts_words(client, db_factory):
    """Platný .xlsx (hlavička + 2 stĺpce) sa naimportuje — regresná poistka opravy."""
    _register(client, "import_ok@example.com")
    cat_id = _create_category(client, db_factory, "import_ok@example.com")

    buf = io.BytesIO()
    pd.DataFrame(
        {"word": ["dog", "cat"], "translation": ["pes", "mačka"]}
    ).to_excel(buf, index=False)

    res = _upload(client, cat_id, buf.getvalue())
    assert res.status_code == 200, res.text
    assert res.json()["imported_count"] == 2


def test_import_wrong_extension_returns_400(client, db_factory):
    _register(client, "import_ext@example.com")
    cat_id = _create_category(client, db_factory, "import_ext@example.com")

    res = _upload(client, cat_id, b"whatever", filename="words.txt")
    assert res.status_code == 400
