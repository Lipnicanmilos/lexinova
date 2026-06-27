"""GDPR — export dát a úplné zmazanie účtu."""


def test_export_includes_account_dates_and_inquiries(client):
    client.post("/api/v1/register", json={"email": "g@example.com", "password": "Abcdef12"})
    client.post("/api/inquiry", json={"email": "g@example.com", "message": "hello there", "page": "/profile"})

    data = client.get("/api/user/export").json()
    info = data.get("export_info", {})
    assert info.get("created_at") is not None
    assert "last_login" in info
    assert any(i["message"] == "hello there" for i in data.get("inquiries", []))


def test_account_deletion_removes_inquiries(client):
    client.post("/api/v1/register", json={"email": "del@example.com", "password": "Abcdef12"})
    client.post("/api/inquiry", json={"email": "del@example.com", "message": "bye", "page": "/x"})
    assert len(client.get("/api/user/export").json().get("inquiries", [])) == 1

    # Zmazanie účtu odstráni aj kontaktné správy viazané na e-mail.
    assert client.delete("/api/user").status_code == 200

    # Po opätovnej registrácii toho istého e-mailu už žiadne staré správy nie sú.
    client.post("/api/v1/register", json={"email": "del@example.com", "password": "Abcdef12"})
    assert len(client.get("/api/user/export").json().get("inquiries", [])) == 0
