"""AI tvorba kategórie z YouTube videa — Gemini aj YouTube overenie sú mockované
(žiadne sieťové volania), testujeme PLUS gating, validáciu odkazu a uloženie slovíčok."""

import pytest

from app.models.user import User
from app.services.ai_category_service import GeminiRateLimited
from app.services.youtube import (
    YouTubeError,
    _parse_iso8601_duration,
    extract_video_id,
)


VIDEO_URL = "https://www.youtube.com/watch?v=8SoLpg_eYTg"


def _register(client, email):
    client.post("/api/v1/register", json={"email": email, "password": "Abcdef12"})


def _set_plus(db_factory, email, value=True):
    db = db_factory()
    try:
        u = db.query(User).filter(User.email == email).first()
        u.is_plus = value
        db.commit()
    finally:
        db.close()


def _fake_generated():
    return {
        "category_name": "Rodičovstvo a telefóny",
        "category_description": "Slovíčka z videa",
        "words": [
            {"original_word": "parent", "translation": "rodič", "language_from": "en", "language_to": "sk"},
            {"original_word": "screen", "translation": "obrazovka", "language_from": "en", "language_to": "sk"},
        ],
    }


def _mock_youtube_ok(monkeypatch):
    async def _fake_validate(url):
        return "8SoLpg_eYTg", "How I parent around smartphones"

    monkeypatch.setattr("app.routers.categories.validate_youtube_url", _fake_validate)


# --- Parsovanie odkazu (čistá funkcia, bez siete) --------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=8SoLpg_eYTg",
        "https://youtu.be/8SoLpg_eYTg",
        "youtube.com/watch?v=8SoLpg_eYTg",
        "https://www.youtube.com/shorts/8SoLpg_eYTg",
        "https://m.youtube.com/watch?v=8SoLpg_eYTg&t=10s",
        "https://www.youtube.com/embed/8SoLpg_eYTg",
    ],
)
def test_extract_video_id_accepts_common_forms(url):
    assert extract_video_id(url) == "8SoLpg_eYTg"


@pytest.mark.parametrize(
    "url",
    [
        "https://vimeo.com/12345",
        "https://evil.com/watch?v=8SoLpg_eYTg",  # cudzia doména sa nesmie dostať do file_uri
        "https://www.youtube.com/watch?v=short",
        "not a url",
        "",
    ],
)
def test_extract_video_id_rejects_bad_urls(url):
    with pytest.raises(YouTubeError):
        extract_video_id(url)


def test_parse_iso8601_duration():
    assert _parse_iso8601_duration("PT8M32S") == 512
    assert _parse_iso8601_duration("PT1H2M3S") == 3723
    assert _parse_iso8601_duration("PT45S") == 45
    assert _parse_iso8601_duration("nonsense") is None


# --- Endpoint --------------------------------------------------------------


def test_create_from_video_requires_auth(client):
    res = client.post("/api/v1/categories/ai-create-from-video", json={"video_url": VIDEO_URL})
    assert res.status_code == 401


def test_create_from_video_rejects_free_user(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    _register(client, "vid_free@example.com")
    res = client.post("/api/v1/categories/ai-create-from-video", json={"video_url": VIDEO_URL})
    assert res.status_code == 403
    assert "PLUS" in res.json()["detail"]


def test_create_from_video_inserts_words_for_plus(client, db_factory, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    _register(client, "vid_plus@example.com")
    _set_plus(db_factory, "vid_plus@example.com")
    _mock_youtube_ok(monkeypatch)

    async def _fake_video(**kwargs):
        # Gemini musí dostať kanonický watch odkaz, nie surový vstup používateľa.
        assert kwargs["video_url"] == VIDEO_URL
        return _fake_generated()

    monkeypatch.setattr(
        "app.routers.categories.generate_category_and_words_from_video_gemini", _fake_video
    )

    res = client.post("/api/v1/categories/ai-create-from-video", json={"video_url": VIDEO_URL})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["category_name"] == "Rodičovstvo a telefóny"
    assert body["inserted_words"] == 2


def test_create_from_video_rejects_bad_video(client, db_factory, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    _register(client, "vid_bad@example.com")
    _set_plus(db_factory, "vid_bad@example.com")

    async def _fake_validate(url):
        raise YouTubeError("Video sa nenašlo alebo nie je verejné.")

    monkeypatch.setattr("app.routers.categories.validate_youtube_url", _fake_validate)

    res = client.post(
        "/api/v1/categories/ai-create-from-video",
        json={"video_url": "https://www.youtube.com/watch?v=ZZZZZZZZZZZ"},
    )
    assert res.status_code == 400


def test_create_from_video_maps_gemini_quota_to_429(client, db_factory, monkeypatch):
    """429 od Gemini nesmie vyjsť von ako 502 — používateľ má vidieť „skús neskôr"."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    _register(client, "vid_429@example.com")
    _set_plus(db_factory, "vid_429@example.com")
    _mock_youtube_ok(monkeypatch)

    async def _fake_video(**kwargs):
        raise GeminiRateLimited("kvóta")

    monkeypatch.setattr(
        "app.routers.categories.generate_category_and_words_from_video_gemini", _fake_video
    )

    res = client.post("/api/v1/categories/ai-create-from-video", json={"video_url": VIDEO_URL})
    assert res.status_code == 429


def test_create_from_video_requires_api_key(client, db_factory, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    _register(client, "vid_nokey@example.com")
    _set_plus(db_factory, "vid_nokey@example.com")

    res = client.post("/api/v1/categories/ai-create-from-video", json={"video_url": VIDEO_URL})
    assert res.status_code == 500
