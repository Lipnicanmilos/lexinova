"""Serverové TTS — neurónové hlasy namiesto hlasov operačného systému.

Dve veci, ktoré tu strážime nadovšetko:

1. **Náklady.** Endpoint smie prehrať iba text, ktorý už v DB je. Otvorený
   `?text=...` by znamenal, že hocikto si objedná syntézu ľubovoľného textu
   na náš účet.
2. **Fallback.** Keď TTS nie je k dispozícii, musí prísť 503 (nie 500) — klient
   z toho pozná, že má použiť `speechSynthesis`, a používateľ nič nezbadá.
"""

import pytest

from app.models.user import User
from app.routers.tts import to_locale
from app.services import tts_service


# ── Pomocníci ───────────────────────────────────────────────────────────────


def _register(client, email):
    res = client.post("/api/v1/register", json={"email": email, "password": "Abcdef12"})
    assert res.status_code == 200, res.text


def _logout(client):
    client.cookies.clear()


def _create_word(client, db_factory, email, original="apple", translation="jablko"):
    db = db_factory()
    try:
        user_id = db.query(User).filter(User.email == email).first().id
    finally:
        db.close()

    cat = client.post(
        "/api/v1/categories", json={"name": "TTS", "description": "", "user_id": user_id}
    )
    assert cat.status_code == 200, cat.text
    cat_id = cat.json()["id"]

    word = client.post(
        "/api/v1/words",
        json={
            "original_word": original,
            "translation": translation,
            "language_from": "en",
            "language_to": "sk",
            "category_id": cat_id,
        },
    )
    assert word.status_code == 200, word.text
    return word.json()["id"]


@pytest.fixture
def tts_on(monkeypatch):
    """Zapne TTS a nahradí syntézu aj bucket — testy nesmú volať Google."""
    monkeypatch.setattr(tts_service, "TTS_ENABLED", True)
    monkeypatch.setattr(tts_service, "TTS_BUCKET", "test-bucket")

    calls = []

    def fake_get_audio(text, lang):
        calls.append((text, lang))
        return b"ID3fake-mp3-bytes"

    monkeypatch.setattr(tts_service, "get_audio", fake_get_audio)
    return calls


# ── Mapovanie jazykov ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "code,expected",
    [("en", "en-US"), ("sk", "sk-SK"), ("no", "nb-NO"), ("en-GB", "en-GB"), ("", "en-US")],
)
def test_locale_ma_region(code, expected):
    """Google bez regiónu hlas často nenájde — holé „sk" nestačí."""
    assert to_locale(code) == expected


# ── Cache kľúče ─────────────────────────────────────────────────────────────


def test_hash_je_stabilny_a_rozlisuje_vstupy():
    a = tts_service.content_hash("apple", "en-US")

    assert a == tts_service.content_hash("apple", "en-US")
    assert a != tts_service.content_hash("apple", "sk-SK")   # iný jazyk
    assert a != tts_service.content_hash("apples", "en-US")  # iný text


# ── Výber hlasu ─────────────────────────────────────────────────────────────


def test_styl_sa_sklada_s_locale(monkeypatch):
    """Chirp 3 HD má naprieč jazykmi rovnaké mená — stačí štýl, nie mapa 24 položiek."""
    monkeypatch.setattr(tts_service, "TTS_VOICE_STYLE", "Chirp3-HD-Achernar")
    monkeypatch.setattr(tts_service, "TTS_VOICES", {})

    assert tts_service.voice_for("sk-SK") == "sk-SK-Chirp3-HD-Achernar"
    assert tts_service.voice_for("en-US") == "en-US-Chirp3-HD-Achernar"


def test_portugalcina_ma_vstavanu_vynimku(monkeypatch):
    """pt-PT Chirp 3 HD nemá; pt-BR ho má, ale s brazílskym prízvukom."""
    monkeypatch.setattr(tts_service, "TTS_VOICE_STYLE", "Chirp3-HD-Achernar")
    monkeypatch.setattr(tts_service, "TTS_VOICES", {})

    assert tts_service.voice_for("pt-PT") == "pt-PT-Wavenet-E"


def test_env_vynimka_prebije_vsetko(monkeypatch):
    monkeypatch.setattr(tts_service, "TTS_VOICE_STYLE", "Chirp3-HD-Achernar")
    monkeypatch.setattr(tts_service, "TTS_VOICES", {"pt-pt": "pt-PT-Standard-E"})

    assert tts_service.voice_for("pt-PT") == "pt-PT-Standard-E"


def test_bez_stylu_vyberie_google(monkeypatch):
    monkeypatch.setattr(tts_service, "TTS_VOICE_STYLE", "")
    monkeypatch.setattr(tts_service, "TTS_VOICES", {})

    assert tts_service.voice_for("sk-SK") == ""


def test_zmena_hlasu_zmeni_cache_kluc(monkeypatch):
    """Inak by po prepnutí hlasu appka ďalej servírovala starý zvuk z bucketu."""
    monkeypatch.setattr(tts_service, "TTS_VOICES", {})
    monkeypatch.setattr(tts_service, "TTS_VOICE_STYLE", "Chirp3-HD-Achernar")
    a = tts_service.content_hash("apple", "en-US")
    monkeypatch.setattr(tts_service, "TTS_VOICE_STYLE", "Chirp3-HD-Charon")

    assert tts_service.content_hash("apple", "en-US") != a


def test_blob_path_je_shardovany():
    """Bez shardu by v buckete vznikol jeden priečinok s desiatkami tisíc súborov."""
    path = tts_service.blob_path("apple", "en-US")
    h = tts_service.content_hash("apple", "en-US")

    assert path == f"tts/{tts_service.TTS_REVISION}/en-us/{h[:2]}/{h}.mp3"


# ── Ochrana rozpočtu ────────────────────────────────────────────────────────


def test_dlhy_text_sa_nesyntetizuje(monkeypatch):
    """Strop zrkadlí Word.original_word = String(100). Bez neho je účet otvorený."""
    monkeypatch.setattr(tts_service, "TTS_ENABLED", True)
    monkeypatch.setattr(tts_service, "TTS_BUCKET", "test-bucket")

    with pytest.raises(tts_service.TTSUnavailable):
        tts_service.get_audio("a" * (tts_service.TTS_MAX_CHARS + 1), "en-US")


def test_prazdny_text_sa_nesyntetizuje(monkeypatch):
    monkeypatch.setattr(tts_service, "TTS_ENABLED", True)
    monkeypatch.setattr(tts_service, "TTS_BUCKET", "test-bucket")

    with pytest.raises(tts_service.TTSUnavailable):
        tts_service.get_audio("   ", "en-US")


def test_nepovoleny_jazyk_sa_nesyntetizuje(monkeypatch):
    """TTS_LANGS drží náklady pod kontrolou pri postupnom rozbiehaní jazykov."""
    monkeypatch.setattr(tts_service, "TTS_ENABLED", True)
    monkeypatch.setattr(tts_service, "TTS_BUCKET", "test-bucket")
    monkeypatch.setattr(tts_service, "TTS_LANGS", ["en"])

    assert tts_service.is_lang_allowed("en-US")
    with pytest.raises(tts_service.TTSUnavailable):
        tts_service.get_audio("jablko", "sk-SK")


def test_vypnute_tts_nesyntetizuje(monkeypatch):
    monkeypatch.setattr(tts_service, "TTS_ENABLED", False)

    with pytest.raises(tts_service.TTSUnavailable):
        tts_service.get_audio("apple", "en-US")


# ── Endpoint ────────────────────────────────────────────────────────────────


def test_bez_prihlasenia_neprehra(client):
    res = client.get("/api/v1/tts/word/1/original.mp3")

    assert res.status_code in (401, 403), res.status_code


def test_vypnute_tts_vracia_503_nie_500(client, db_factory):
    """503 = „pouzi speechSynthesis". 500 by navyse poslalo e-mail alert."""
    _register(client, "tts_off@example.com")
    word_id = _create_word(client, db_factory, "tts_off@example.com")

    res = client.get(f"/api/v1/tts/word/{word_id}/original.mp3")

    assert res.status_code == 503, res.text


def test_neznama_strana_kartcky(client, db_factory, tts_on):
    _register(client, "tts_side@example.com")
    word_id = _create_word(client, db_factory, "tts_side@example.com")

    assert client.get(f"/api/v1/tts/word/{word_id}/bok.mp3").status_code == 404


def test_cudzie_slovo_je_neviditelne(client, db_factory, tts_on):
    """404, nie 403 — endpoint nesmie prezradiť, ktoré id existujú."""
    _register(client, "tts_owner@example.com")
    word_id = _create_word(client, db_factory, "tts_owner@example.com")

    _logout(client)
    _register(client, "tts_intruder@example.com")

    res = client.get(f"/api/v1/tts/word/{word_id}/original.mp3")

    assert res.status_code == 404, res.text
    assert not tts_on, "cudzie slovo sa nesmie ani zacat syntetizovat"


def test_neexistujuce_slovo(client, db_factory, tts_on):
    _register(client, "tts_missing@example.com")
    _create_word(client, db_factory, "tts_missing@example.com")

    assert client.get("/api/v1/tts/word/999999/original.mp3").status_code == 404


def test_vracia_mp3_s_cache_hlavickami(client, db_factory, tts_on):
    _register(client, "tts_ok@example.com")
    word_id = _create_word(client, db_factory, "tts_ok@example.com")

    res = client.get(f"/api/v1/tts/word/{word_id}/original.mp3")

    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "audio/mpeg"
    assert res.content == b"ID3fake-mp3-bytes"
    # Bez cache by kazde prehratie znamenalo platenu syntezu.
    assert "max-age" in res.headers["cache-control"]
    assert "private" in res.headers["cache-control"]
    assert res.headers["etag"]


def test_strany_kartcky_citaju_spravny_jazyk(client, db_factory, tts_on):
    """Preklad sa musí čítať slovenským hlasom, nie anglickým."""
    _register(client, "tts_lang@example.com")
    word_id = _create_word(client, db_factory, "tts_lang@example.com")

    client.get(f"/api/v1/tts/word/{word_id}/original.mp3")
    client.get(f"/api/v1/tts/word/{word_id}/translation.mp3")

    assert tts_on == [("apple", "en-US"), ("jablko", "sk-SK")]


def test_etag_setri_prenos(client, db_factory, tts_on):
    _register(client, "tts_etag@example.com")
    word_id = _create_word(client, db_factory, "tts_etag@example.com")

    first = client.get(f"/api/v1/tts/word/{word_id}/original.mp3")
    again = client.get(
        f"/api/v1/tts/word/{word_id}/original.mp3",
        headers={"If-None-Match": first.headers["etag"]},
    )

    assert again.status_code == 304
    assert again.content == b""


# ── Klient ──────────────────────────────────────────────────────────────────


def test_modul_pozna_adresu_zvuku(client):
    js = client.get("/static/js/speech.js").text

    assert "wordAudioUrl" in js
    assert "/api/v1/tts/word/" in js


def test_opakovanie_posiela_zvuk_do_prehravaca(client):
    _register(client, "tts_repeat@example.com")

    page = client.get("/repeat").text

    assert "wordAudioUrl" in page
    # tempo rieši prehrávač, nie syntéza — inak platíme nahrávku za každú rýchlosť
    assert "playbackRate" in client.get("/static/js/speech.js").text


def test_prehravanie_ma_casovy_strop(client):
    """Pomaly sa načítavajúce audio nevyvolá onended ani onerror — bez stropu
    `await` v auto-play slučke zamrzne natrvalo (stalo sa na prode 2026-08-15)."""
    js = client.get("/static/js/speech.js").text

    assert "LOAD_TIMEOUT_MS" in js
    assert "onplaying" in js  # strop sa po rozohraní nahradí poistkou na dĺžku


def test_zvuk_sa_predohrieva(client):
    """Bez predohrevu čaká používateľ po stlačení Play na syntézu prvého slova."""
    assert "prefetch" in client.get("/static/js/speech.js").text

    _register(client, "tts_warm@example.com")
    page = client.get("/repeat").text

    assert "warmFirstWords" in page
    assert "warmWord" in page


def test_sw_verzia_bola_zvysena(client):
    """speech.js je v precache — bez bumpu by opravu dostali len noví používatelia."""
    sw = client.get("/sw.js").text

    assert "lexinova-v52" in sw
    assert "'/static/js/speech.js'" in sw


def test_vypnute_tts_klient_ani_neskusa(client):
    """Inak by auto-play vypálil 503-ku na každé slovo, kým naskočí fallback."""
    _register(client, "tts_flag_off@example.com")

    assert "window.LEXI_TTS = false" in client.get("/repeat").text


def test_zapnute_tts_klient_pouzije(client, tts_on):
    _register(client, "tts_flag_on@example.com")

    assert "window.LEXI_TTS = true" in client.get("/repeat").text
