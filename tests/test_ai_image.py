"""AI tvorba kategórie z fotky/screenshotu — vision služba je mockovaná
(žiadne reálne volanie na AI), testujeme validáciu uploadu + uloženie slovíčok."""


def _register(client, email):
    client.post("/api/v1/register", json={"email": email, "password": "Abcdef12"})


def _fake_generated():
    return {
        "category_name": "Cestovanie",
        "category_description": "Slovíčka z fotky",
        "words": [
            {"original_word": "airport", "translation": "letisko", "language_from": "en", "language_to": "sk"},
            {"original_word": "ticket", "translation": "lístok", "language_from": "en", "language_to": "sk"},
        ],
    }


def test_create_from_image_inserts_words(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    async def _fake_vision(**kwargs):
        return _fake_generated()

    monkeypatch.setattr(
        "app.routers.categories.generate_category_and_words_from_image_claude", _fake_vision
    )

    _register(client, "img1@example.com")
    res = client.post(
        "/api/v1/categories/ai-create-from-image",
        files={"image": ("vocab.png", b"\x89PNG\r\n_fake_image_bytes", "image/png")},
        data={"language_from": "en", "language_to": "sk"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["category_name"] == "Cestovanie"
    assert body["inserted_words"] == 2


def test_create_from_image_rejects_non_image(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    _register(client, "img2@example.com")
    res = client.post(
        "/api/v1/categories/ai-create-from-image",
        files={"image": ("notes.txt", b"hello", "text/plain")},
        data={"language_from": "en", "language_to": "sk"},
    )
    assert res.status_code == 400


def test_create_from_image_requires_auth(client):
    res = client.post(
        "/api/v1/categories/ai-create-from-image",
        files={"image": ("vocab.png", b"\x89PNG data", "image/png")},
        data={"language_from": "en", "language_to": "sk"},
    )
    assert res.status_code == 401
