"""Ukážka na /demo — živé AI generovanie pre neprihláseného návštevníka.

Overuje tri poistky proti spáleniu kvóty (cache, denný strop, náhradná sada)
a to, že návštevník nikdy neuvidí chybu namiesto slovíčok.
Žiadne sieťové volania — AI je vždy mocknutá.
"""
import json

import pytest

from app.models.demo_generation import DemoGeneration
from app.services import demo_service


def _fake_payload(words=None):
    return {
        "category_name": "Na letisku",
        "category_description": "Slovíčka na letisko",
        "words": words or [
            {"original_word": "gate", "translation": "brána"},
            {"original_word": "delay", "translation": "meškanie"},
        ],
    }


@pytest.fixture
def fake_ai(monkeypatch):
    """Gemini vráti pripravený payload; kľúč musí existovať, inak sa preskočí."""
    calls = []

    async def _fake(**kwargs):
        calls.append(kwargs)
        return _fake_payload()

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("app.routers.demo.generate_category_and_words_gemini", _fake)
    return calls


@pytest.fixture(autouse=True)
def _clean_demo_rows(db_factory):
    yield
    db = db_factory()
    try:
        db.query(DemoGeneration).delete()
        db.commit()
    finally:
        db.close()


# ── Normalizácia témy ──

def test_normalize_topic_ignores_case_diacritics_and_spacing():
    assert demo_service.normalize_topic("Cestovanie  Lietadlom") == "cestovanie lietadlom"
    assert demo_service.normalize_topic("cestovanie lietadlom") == "cestovanie lietadlom"
    # Diakritika aj interpunkcia idú preč, inak by cache minula skoro každú tému.
    assert demo_service.normalize_topic("U lekára!") == "u lekara"


def test_normalize_topic_empty_for_punctuation_only():
    assert demo_service.normalize_topic("!!!") == ""


# ── Generovanie ──

def test_generate_calls_ai_and_caches_result(client, fake_ai, db_factory):
    res = client.post("/api/v1/demo/generate", json={"topic": "na letisku"})
    assert res.status_code == 200
    body = res.json()
    assert body["source"] == "ai"
    assert [w["original"] for w in body["words"]] == ["gate", "delay"]
    assert len(fake_ai) == 1

    db = db_factory()
    try:
        row = db.query(DemoGeneration).filter(DemoGeneration.topic_key == "na letisku").first()
        assert row is not None
        assert json.loads(row.words_json)[0]["translation"] == "brána"
    finally:
        db.close()


def test_second_request_for_same_topic_is_served_from_cache(client, fake_ai):
    client.post("/api/v1/demo/generate", json={"topic": "na letisku"})
    res = client.post("/api/v1/demo/generate", json={"topic": "  Na Letisku  "})

    assert res.status_code == 200
    assert res.json()["source"] == "cache"
    # Kľúčové: druhá požiadavka nesmie volať AI.
    assert len(fake_ai) == 1


def test_daily_cap_serves_prepared_set_instead_of_error(client, fake_ai, monkeypatch):
    monkeypatch.setattr(demo_service, "DEMO_AI_DAILY_LIMIT", 1)
    client.post("/api/v1/demo/generate", json={"topic": "prva tema"})

    res = client.post("/api/v1/demo/generate", json={"topic": "druha tema"})
    assert res.status_code == 200
    body = res.json()
    assert body["source"] == "sample"
    assert body["requested_topic"] == "druha tema"
    assert body["words"]                      # návštevník vždy niečo dostane
    assert len(fake_ai) == 1                  # druhá téma už AI nevolala


def test_ai_failure_falls_back_to_prepared_set(client, monkeypatch):
    async def _boom(**kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("app.routers.demo.generate_category_and_words_gemini", _boom)

    res = client.post("/api/v1/demo/generate", json={"topic": "co s tym"})
    assert res.status_code == 200
    assert res.json()["source"] == "sample"
    assert res.json()["words"]


def test_topic_of_punctuation_only_is_rejected(client, fake_ai):
    res = client.post("/api/v1/demo/generate", json={"topic": "!!!"})
    assert res.status_code == 400
    assert not fake_ai


def test_too_long_topic_is_rejected_before_ai(client, fake_ai):
    res = client.post("/api/v1/demo/generate", json={"topic": "x" * 200})
    assert res.status_code == 422
    assert not fake_ai


# ── Spracovanie výstupu AI ──

def test_words_are_deduped_and_capped(client, monkeypatch):
    async def _dupes(**kwargs):
        return _fake_payload([
            {"original_word": "gate", "translation": "brána"},
            {"original_word": "Gate", "translation": "východ"},   # to isté heslo inak
            {"original_word": "", "translation": "nič"},           # prázdne
            {"original_word": "delay", "translation": "meškanie"},
            {"original_word": "luggage", "translation": "batožina"},
            {"original_word": "seat", "translation": "sedadlo"},
            {"original_word": "crew", "translation": "posádka"},
            {"original_word": "runway", "translation": "dráha"},   # cez limit 5
        ])

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("app.routers.demo.generate_category_and_words_gemini", _dupes)

    words = client.post("/api/v1/demo/generate", json={"topic": "letisko"}).json()["words"]
    assert len(words) == demo_service.DEMO_WORD_COUNT
    originals = [w["original"] for w in words]
    assert originals.count("gate") == 1
    assert "Gate" not in originals
    assert "" not in originals
