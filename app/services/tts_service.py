"""Serverové TTS — neurónové hlasy pre kartičky a Opakovanie.

Prehliadačové `speechSynthesis` znie na každom zariadení inak (Windows číta
robotickým Microsoft hlasom, pre sk/hr/sl často nemá hlas vôbec). Tu si zvuk
vyrobíme sami cez Google Cloud TTS a uložíme ho ako MP3.

Ekonomika stojí a padá na cache: slovná zásoba je uzavretá množina, ktorá sa
enormne opakuje — „apple" syntetizujeme RAZ pre celú appku a odvtedy len
servírujeme súbor. Účtovná jednotka je dvojica (text, jazyk), nie prehratie.

Vrstvy: GCS bucket → HTTP cache prehliadača → service worker → a keď zlyhá
všetko, klient spadne späť na `speechSynthesis`. Nikdy teda nie je horšie
než pred touto zmenou.

Bez `TTS_ENABLED=true` je modul úplne neaktívny — lokálny vývoj aj testy
bežia ďalej bez GCP prihlasovacích údajov.
"""

import hashlib
import json
import os
import threading
from typing import Optional

from app.services.runtime import logger

# ── Konfigurácia ────────────────────────────────────────────────────────────

TTS_ENABLED = os.getenv("TTS_ENABLED", "false").lower() == "true"
TTS_BUCKET = os.getenv("TTS_BUCKET", "").strip()

# Zhoda s `Word.original_word` / `Word.translation` (String(100)). Strop je tu
# druhýkrát zámerne: bráni tomu, aby sa cez chybu inde dal objednať drahý
# dlhý text.
TTS_MAX_CHARS = 100

# Jazyky, pre ktoré sa smie syntetizovať. Prázdne = všetky. Počas rozbehu
# drží náklady pod kontrolou a umožní púšťať to po jednom jazyku.
TTS_LANGS = [
    x.strip().lower() for x in (os.getenv("TTS_LANGS", "") or "").split(",") if x.strip()
]

# Mapovanie locale → konkrétny hlas, napr.
#   TTS_VOICES='{"en-US": "en-US-Chirp3-HD-Achernar"}'
# Prázdne pre daný jazyk = necháme Google vybrať predvolený hlas. Reálne mená
# hlasov pre svoje jazyky si vypíš cez `scripts/list_tts_voices.py`.
def _load_voice_map() -> dict:
    raw = os.getenv("TTS_VOICES", "") or ""
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
        return {str(k).lower(): str(v) for k, v in parsed.items()} if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        logger.warning("TTS_VOICES nie je platny JSON — pouzivam predvolene hlasy")
        return {}


TTS_VOICES = _load_voice_map()

# Verzia zvukovej sady. Zmeň, keď zmeníš hlas/formát — dostaneš tým nové
# cache kľúče a stará vrstva sa prestane používať bez mazania bucketu.
TTS_REVISION = os.getenv("TTS_REVISION", "v1")


class TTSUnavailable(RuntimeError):
    """TTS je vypnuté, nenakonfigurované alebo dočasne zlyhalo.

    Router to prekladá na 503 a klient sa vráti k `speechSynthesis`.
    """


# ── Lazy klienti ────────────────────────────────────────────────────────────
# Importujeme až pri prvom použití, aby appka (a testy) bežali aj bez
# nainštalovaných google-cloud knižníc.

_lock = threading.Lock()
_tts_client = None
_bucket = None


def _get_tts_client():
    global _tts_client
    if _tts_client is None:
        with _lock:
            if _tts_client is None:
                try:
                    from google.cloud import texttospeech
                except ImportError as exc:
                    raise TTSUnavailable("google-cloud-texttospeech nie je nainstalovane") from exc
                _tts_client = texttospeech.TextToSpeechClient()
    return _tts_client


def _get_bucket():
    global _bucket
    if _bucket is None:
        with _lock:
            if _bucket is None:
                try:
                    from google.cloud import storage
                except ImportError as exc:
                    raise TTSUnavailable("google-cloud-storage nie je nainstalovane") from exc
                _bucket = storage.Client().bucket(TTS_BUCKET)
    return _bucket


# ── Cache kľúče ─────────────────────────────────────────────────────────────


def content_hash(text: str, lang: str) -> str:
    """Obsahový odtlačok — mení sa s textom, jazykom, hlasom aj revíziou.

    Rýchlosť reči zámerne NIE je v kľúči: klient ju rieši cez
    `audio.playbackRate`, takže jedna nahrávka pokryje všetky tempá.
    """
    voice = TTS_VOICES.get(lang.lower(), "")
    raw = f"{TTS_REVISION}|{lang.lower()}|{voice}|{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def blob_path(text: str, lang: str) -> str:
    """Cesta v buckete. Prvé dva znaky hashu ako shard — bucket sa tak
    nezvrhne na jeden priečinok s desiatkami tisíc položiek."""
    h = content_hash(text, lang)
    return f"tts/{TTS_REVISION}/{lang.lower()}/{h[:2]}/{h}.mp3"


# ── Syntéza a úložisko ──────────────────────────────────────────────────────


def is_configured() -> bool:
    return bool(TTS_ENABLED and TTS_BUCKET)


def is_lang_allowed(lang: str) -> bool:
    if not TTS_LANGS:
        return True
    lang = (lang or "").lower()
    base = lang.split("-")[0]
    return lang in TTS_LANGS or base in TTS_LANGS


def _synthesize(text: str, lang: str) -> bytes:
    """Zavolá Google Cloud TTS. Vracia MP3 bajty."""
    from google.cloud import texttospeech

    client = _get_tts_client()
    voice_name = TTS_VOICES.get(lang.lower(), "")

    voice_params = texttospeech.VoiceSelectionParams(language_code=lang)
    if voice_name:
        voice_params.name = voice_name

    # `speaking_rate` nenastavujeme — tempo je vec klienta (playbackRate),
    # inak by sme pre každé tempo platili vlastnú nahrávku.
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
    )

    response = client.synthesize_speech(
        input=texttospeech.SynthesisInput(text=text),
        voice=voice_params,
        audio_config=audio_config,
    )
    return response.audio_content


def get_audio(text: str, lang: str) -> bytes:
    """Vráti MP3 pre (text, jazyk) — z bucketu, inak vyrobí a uloží.

    Zdvihne `TTSUnavailable`, keď sa zvuk nedá dodať; volajúci to má preložiť
    na 503, nie na 500 — nie je to chyba, len sa ide fallbackom.
    """
    if not is_configured():
        raise TTSUnavailable("TTS nie je zapnute (TTS_ENABLED/TTS_BUCKET)")

    text = (text or "").strip()
    if not text:
        raise TTSUnavailable("prazdny text")
    if len(text) > TTS_MAX_CHARS:
        raise TTSUnavailable(f"text presahuje {TTS_MAX_CHARS} znakov")
    if not is_lang_allowed(lang):
        raise TTSUnavailable(f"jazyk {lang} nie je povoleny (TTS_LANGS)")

    path = blob_path(text, lang)

    # 1) Cache hit — drvivá väčšina požiadaviek, žiadna platba za syntézu.
    try:
        blob = _get_bucket().blob(path)
        cached = blob.download_as_bytes()
        if cached:
            return cached
    except TTSUnavailable:
        raise
    except Exception as exc:  # NotFound aj výpadok GCS — ideme syntetizovať
        if exc.__class__.__name__ != "NotFound":
            logger.warning(f"TTS cache read zlyhal ({path}): {exc}")

    # 2) Cache miss — vyrob a ulož.
    try:
        audio = _synthesize(text, lang)
    except TTSUnavailable:
        raise
    except Exception as exc:
        logger.error(f"TTS synteza zlyhala pre {lang!r}: {exc}")
        raise TTSUnavailable("synteza zlyhala") from exc

    if not audio:
        raise TTSUnavailable("synteza vratila prazdny zvuk")

    try:
        _get_bucket().blob(path).upload_from_string(audio, content_type="audio/mpeg")
    except Exception as exc:
        # Zvuk máme — neuložiť ho je len drahšie, nie chyba pre používateľa.
        logger.warning(f"TTS cache write zlyhal ({path}): {exc}")

    return audio
