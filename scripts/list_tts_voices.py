"""Vypíše hlasy, ktoré Google Cloud TTS ponúka pre naše jazyky.

Odpovedá na otázku „pokrýva Chirp 3: HD všetkých 24 jazykov, ktoré appka
používa?" — a rovno dá presné mená hlasov do `TTS_VOICES`.

    python scripts/list_tts_voices.py            # len prémiové (Chirp/Neural/Studio)
    python scripts/list_tts_voices.py --all      # vrátane štandardných

Potrebuje prihlásenie do GCP:
    gcloud auth application-default login
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.routers.tts import LOCALE_BY_CODE  # noqa: E402

PREMIUM_MARKERS = ("chirp", "neural", "studio", "wavenet", "polyglot")


def main() -> int:
    show_all = "--all" in sys.argv

    try:
        from google.cloud import texttospeech
    except ImportError:
        print("Chyba: chyba google-cloud-texttospeech (pip install -r requirements.txt)")
        return 1

    try:
        client = texttospeech.TextToSpeechClient()
        voices = client.list_voices().voices
    except Exception as exc:
        print(f"Chyba pri volani Google TTS: {exc}")
        print("Tip: gcloud auth application-default login")
        return 1

    by_locale: dict[str, list[str]] = {}
    for v in voices:
        for code in v.language_codes:
            by_locale.setdefault(code, []).append(v.name)

    missing = []
    print(f"{'JAZYK':<8} {'LOCALE':<8} HLASY")
    print("-" * 72)

    for code, locale in sorted(LOCALE_BY_CODE.items()):
        names = by_locale.get(locale, [])
        if not show_all:
            names = [n for n in names if any(m in n.lower() for m in PREMIUM_MARKERS)]
        names.sort()

        if not names:
            missing.append(f"{code} ({locale})")
            print(f"{code:<8} {locale:<8} — ziadne —")
            continue

        print(f"{code:<8} {locale:<8} {names[0]}")
        for extra in names[1:]:
            print(f"{'':<17} {extra}")

    print("-" * 72)
    if missing:
        label = "premiovy hlas" if not show_all else "hlas"
        print(f"Bez {label}u ({len(missing)}): {', '.join(missing)}")
        print("Pre tieto jazyky bud necha TTS_VOICES prazdne (Google vyberie sam),")
        print("alebo zvaz Azure Neural — ma sirsie pokrytie CEE jazykov.")
    else:
        print("Vsetky jazyky pokryte.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
