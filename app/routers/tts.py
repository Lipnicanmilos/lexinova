"""Zvuk slovíčok — neurónové TTS namiesto hlasov operačného systému.

Endpoint zámerne NEBERIE text, ale `word_id`. Otvorený `?text=...` by znamenal,
že ktokoľvek si môže objednať syntézu ľubovoľného textu na náš účet; takto sa
dá prehrať výhradne to, čo už v databáze je, a čo daný používateľ smie vidieť.

Zvuk tečie cez našu doménu, nie priamo z GCS — CSP v `main.py` má
`default-src 'self'` bez `media-src`, takže cudzí origin by prehliadač zablokoval.
Bucket tak navyše ostáva privátny.

Keď TTS nie je k dispozícii, vraciame 503 (nie 500): nie je to chyba, len
signál pre klienta, nech použije `speechSynthesis` ako doteraz.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.category import Category
from app.models.user import User
from app.models.word import Word
from app.services.class_access import is_class_member_category
from app.services.runtime import limiter
from app.services.session_auth import get_authenticated_user
from app.services import tts_service

router = APIRouter(prefix="/api/v1/tts", tags=["tts"])

SIDES = {"original", "translation"}

# Krátky kód z DB („en") → locale pre TTS („en-US"). Zrkadlí `LOCALE_BY_CODE`
# v `static/js/speech.js`; Google bez regiónu hlas často nenájde.
LOCALE_BY_CODE = {
    "en": "en-US", "sk": "sk-SK", "de": "de-DE", "fr": "fr-FR", "es": "es-ES",
    "cs": "cs-CZ", "it": "it-IT", "pl": "pl-PL", "ru": "ru-RU", "hu": "hu-HU",
    "pt": "pt-PT", "nl": "nl-NL", "uk": "uk-UA", "ro": "ro-RO", "sv": "sv-SE",
    "da": "da-DK", "no": "nb-NO", "fi": "fi-FI", "tr": "tr-TR", "el": "el-GR",
    "hr": "hr-HR", "sr": "sr-RS", "bg": "bg-BG", "sl": "sl-SI",
}


def to_locale(code: str) -> str:
    code = (code or "").strip()
    if not code:
        return "en-US"
    if "-" in code:
        return code
    return LOCALE_BY_CODE.get(code.lower(), code)


def _resolve_word(db: Session, user: User, word_id: int) -> Word:
    """Vráti slovo, ak naň používateľ má nárok — vlastník kategórie alebo
    člen triedy, ktorej je kategória zdieľaná. Inak 404 (nie 403, nech
    endpoint neprezrádza, ktoré id existujú)."""
    word = db.query(Word).filter(Word.id == word_id).first()
    if not word:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Word not found")

    owns = (
        db.query(Category.id)
        .filter(Category.id == word.category_id, Category.user_id == user.id)
        .first()
        is not None
    )
    if owns or is_class_member_category(db, user.id, word.category_id):
        return word

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Word not found")


@router.get("/word/{word_id}/{side}.mp3")
@limiter.limit("600/hour")  # auto-play prejde stovky slov za reláciu
def word_audio(
    word_id: int,
    side: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """MP3 pre jednu stranu kartičky (`original` | `translation`)."""
    if side not in SIDES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown side")

    if not tts_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="TTS disabled"
        )

    word = _resolve_word(db, current_user, word_id)

    if side == "original":
        text, lang = word.original_word, word.language_from
    else:
        text, lang = word.translation, word.language_to

    lang = to_locale(lang)

    try:
        audio = tts_service.get_audio(text, lang)
    except tts_service.TTSUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    # ETag je obsahový odtlačok — po úprave slovíčka sa zmení a prehliadač si
    # pri revalidácii vypýta nový zvuk. `private`, lebo odpoveď je za prihlásením.
    etag = f'"{tts_service.content_hash(text, lang)[:32]}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})

    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "private, max-age=604800",  # 7 dní
            "ETag": etag,
        },
    )
