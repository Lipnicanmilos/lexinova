import base64
import os
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.category import Category
from app.models.user import User
from app.models.word import Word
from app.schemas.category import (
    CategoryCreate,
    CategoryResponse,
    CategoryShareResponse,
    CategoryUpdate,
    SharedCategoryImportRequest,
    SharedCategoryImportResponse,
    SharedCategoryPreview,
)
from app.schemas.ai_category import (
    AICategoryCreateRequest,
    AICategoryCreateResponse,
    AICategoryFromVideoRequest,
)
from app.services.ai_category_service import (
    GeminiRateLimited,
    generate_category_and_words_claude,
    generate_category_and_words_from_image_claude,
    generate_category_and_words_from_image_gemini,
    generate_category_and_words_from_image_groq,
    generate_category_and_words_from_video_gemini,
    generate_category_and_words_gemini,
    generate_category_and_words_groq,
    validate_ai_category_payload,
)
from app.services.youtube import YouTubeError, canonical_watch_url, validate_youtube_url
from app.services.limits import (
    CATEGORY_LIMIT_FREE,
    consume_ai_quota,
    refund_ai_quota,
    word_limit_for,
)
from app.services.session_auth import get_authenticated_user
from app.services.runtime import limiter, logger
from app.services.stats_service import (
    empty_level_counts,
    empty_level_counts_float,
    get_category_word_summary,
)


router = APIRouter(prefix="/api/v1/categories", tags=["categories"])

# Tvorba kategórie z fotky (AI vision)
IMAGE_MAX_BYTES = 5 * 1024 * 1024  # 5 MB (limit Claude vision na obrázok)
IMAGE_ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
IMAGE_MAX_WORDS = 60

# Tvorba kategórie z YouTube videa (AI, len Gemini — Groq/Claude URL nestiahnu)
VIDEO_MAX_WORDS = 100

# Zdieľanie sady kódom/linkom (Fáza 1 učiteľského kanála).
# Abeceda bez zameniteľných znakov (O/0, I/1/L) — kód sa diktuje aj nahlas v triede.
SHARE_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
SHARE_CODE_LENGTH = 8
SITE_URL = os.getenv("SITE_URL", "https://lexinova.fun").rstrip("/")


def _get_category_limit(user: User) -> Optional[int]:
    """None = neobmedzene (PLUS). Free účet má limit CATEGORY_LIMIT_FREE."""
    return None if user.is_plus else CATEGORY_LIMIT_FREE


AI_PROVIDER_KEYS = {
    "claude": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
}


def _provider_chain(requested: str) -> list[str]:
    """Poradie AI providerov: Gemini je predvolený (free tier), pri zlyhaní
    sa automaticky skúsi Groq. Claude len na explicitné vyžiadanie (platený
    API kredit). Vráti len providerov s nastaveným API kľúčom."""
    if requested == "claude":
        chain = ["claude", "gemini", "groq"]
    elif requested == "groq":
        chain = ["groq", "gemini"]
    else:
        chain = ["gemini", "groq"]
    return [p for p in chain if os.getenv(AI_PROVIDER_KEYS[p])]


def _persist_generated_category(
    db: Session,
    user: User,
    generated: dict,
    default_language_from: str,
    default_language_to: str,
    word_limit: Optional[int] = None,
) -> AICategoryCreateResponse:
    """Zvaliduje AI payload, vytvorí/nájde kategóriu a uloží slovíčka.

    Zdieľané medzi tvorbou z promptu aj z obrázka. Limit kategórií treba
    skontrolovať PRED volaním AI (aby sa nemíňali API credits). `word_limit`
    (None = neobmedzene) obmedzí počet nových slov v kategórii pre Free účet."""
    try:
        validate_ai_category_payload(generated)
    except Exception as exc:
        # Nezhadzuj celý request kvôli pár chybným slovám — ukladacia slučka
        # nižšie chybné položky preskočí. Zaloguj pre diagnostiku.
        logger.warning("AI payload failed strict validation: %s | payload: %.500s", exc, generated)

    category_name = generated.get("category_name")
    if not category_name:
        logger.warning("AI payload missing category_name | payload: %.500s", generated)
        raise HTTPException(status_code=400, detail="AI did not return category_name")

    category_description = generated.get("category_description")

    existing_category = (
        db.query(Category)
        .filter(Category.name == category_name, Category.user_id == user.id)
        .first()
    )
    if existing_category:
        category = existing_category
    else:
        category = Category(name=category_name, description=category_description, user_id=user.id)
        db.add(category)
        db.commit()
        db.refresh(category)

    words = generated.get("words") or []
    if not isinstance(words, list):
        raise HTTPException(status_code=400, detail="AI payload words must be a list")

    inserted = 0
    updated = 0
    skipped = 0
    saved_words_preview: list[dict] = []

    # Aktuálny počet slov v kategórii (kvôli word_limit pre Free účet).
    current_word_count = (
        db.query(func.count(Word.id))
        .filter(Word.category_id == category.id, Word.user_id == user.id)
        .scalar()
        or 0
    )

    for w in words:
        try:
            original_word = str(w.get("original_word", "")).strip()
            translation = str(w.get("translation", "")).strip()
            language_from = str(w.get("language_from", default_language_from)).strip()
            language_to = str(w.get("language_to", default_language_to)).strip()
        except Exception:
            skipped += 1
            continue

        if not original_word or not translation:
            skipped += 1
            continue

        existing_word = (
            db.query(Word)
            .filter(
                Word.category_id == category.id,
                Word.original_word == original_word,
                Word.user_id == user.id,
            )
            .first()
        )

        if existing_word:
            if existing_word.translation != translation:
                existing_word.translation = translation
                existing_word.language_from = language_from
                existing_word.language_to = language_to
                updated += 1
            else:
                skipped += 1
            continue

        # Free účet: nepridávaj nad word_limit (existujúce slová sa stále aktualizujú).
        if word_limit is not None and current_word_count >= word_limit:
            skipped += 1
            continue

        new_word = Word(
            original_word=original_word,
            translation=translation,
            category_id=category.id,
            user_id=user.id,
            language_from=language_from,
            language_to=language_to,
        )
        db.add(new_word)
        inserted += 1
        current_word_count += 1

        saved_words_preview.append(
            {
                "original_word": original_word,
                "translation": translation,
                "language_from": language_from,
                "language_to": language_to,
            }
        )

    db.commit()

    return AICategoryCreateResponse(
        category_id=category.id,
        category_name=category.name,
        category_description=category.description,
        inserted_words=inserted,
        skipped_words=skipped + updated,
        words=[
            {
                "original_word": sw["original_word"],
                "translation": sw["translation"],
                "language_from": sw["language_from"],
                "language_to": sw["language_to"],
            }
            for sw in saved_words_preview
        ],
    )


def _get_current_user(request: Request, db: Session) -> User:
    return get_authenticated_user(request, db)


@router.get("", response_model=list[CategoryResponse])
async def get_categories(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    categories = db.query(Category).filter(Category.user_id == user.id).all()
    summaries = get_category_word_summary(db, user.id, [category.id for category in categories])

    result = []
    for category in categories:
        summary = summaries.get(
            category.id,
            {
                "total_words": 0,
                "level_counts": empty_level_counts(),
                "level_percentages": empty_level_counts_float(),
            },
        )
        result.append(
            CategoryResponse(
                id=category.id,
                name=category.name,
                description=category.description,
                user_id=category.user_id,
                created_at=category.created_at,
                share_code=category.share_code,
                total_words=summary["total_words"],
                level_counts=summary["level_counts"],
                level_percentages=summary["level_percentages"],
            )
        )
    return result


@router.post("", response_model=CategoryResponse)
async def create_category(
    category_data: CategoryCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_current_user(request, db)

    category_count = db.query(Category).filter(Category.user_id == user.id).count()
    limit = _get_category_limit(user)
    if limit is not None and category_count >= limit:
        raise HTTPException(
            status_code=400,
            detail=f"Dosiahli ste maximum {limit} kategórií. Aktivujte PLUS pre neobmedzené kategórie.",
        )

    existing_category = (
        db.query(Category)
        .filter(Category.name == category_data.name, Category.user_id == user.id)
        .first()
    )
    if existing_category:
        raise HTTPException(status_code=400, detail="Category with this name already exists")

    new_category = Category(
        name=category_data.name,
        description=category_data.description,
        user_id=user.id,
    )
    db.add(new_category)
    db.commit()
    db.refresh(new_category)
    return new_category


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    category_update: CategoryUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_current_user(request, db)
    category = (
        db.query(Category)
        .filter(Category.id == category_id, Category.user_id == user.id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    for field, value in category_update.dict(exclude_unset=True).items():
        setattr(category, field, value)

    db.commit()
    db.refresh(category)

    summary = get_category_word_summary(db, user.id, [category.id])[category.id]
    return CategoryResponse(
        id=category.id,
        name=category.name,
        description=category.description,
        created_at=category.created_at,
        user_id=category.user_id,
        total_words=summary["total_words"],
        level_counts=summary["level_counts"],
        level_percentages=summary["level_percentages"],
    )


@router.delete("/{category_id}")
async def delete_category(category_id: int, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)

    category = (
        db.query(Category)
        .filter(Category.id == category_id, Category.user_id == user.id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    db.delete(category)
    db.commit()
    return {"message": "Category deleted successfully"}


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category_detail(category_id: int, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    category = (
        db.query(Category)
        .filter(Category.id == category_id, Category.user_id == user.id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    summary = get_category_word_summary(db, user.id, [category.id])[category.id]
    return CategoryResponse(
        id=category.id,
        name=category.name,
        description=category.description,
        user_id=category.user_id,
        created_at=category.created_at,
        share_code=category.share_code,
        total_words=summary["total_words"],
        level_counts=summary["level_counts"],
        level_percentages=summary["level_percentages"],
    )


# ── Zdieľanie sady kódom/linkom (Fáza 1 učiteľského kanála) ──

def _generate_share_code(db: Session) -> str:
    """Unikátny kód (31^8 kombinácií) — kolízia je takmer vylúčená, retry + unique
    index v DB sú poistky."""
    for _ in range(5):
        code = "".join(secrets.choice(SHARE_CODE_ALPHABET) for _ in range(SHARE_CODE_LENGTH))
        if not db.query(Category).filter(Category.share_code == code).first():
            return code
    raise HTTPException(status_code=500, detail="Nepodarilo sa vygenerovať zdieľací kód.")


@router.post("/{category_id}/share", response_model=CategoryShareResponse)
async def share_category(category_id: int, request: Request, db: Session = Depends(get_db)):
    """Vygeneruje (alebo vráti existujúci) zdieľací kód sady.

    Zámerne bez PLUS paywallu — každý zdieľaný link je akvizičný kanál
    (viralita je celý zmysel Fázy 1 učiteľského kanála)."""
    user = _get_current_user(request, db)
    category = (
        db.query(Category)
        .filter(Category.id == category_id, Category.user_id == user.id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    if not category.share_code:
        category.share_code = _generate_share_code(db)
        db.commit()

    return CategoryShareResponse(
        share_code=category.share_code,
        share_url=f"{SITE_URL}/s/{category.share_code}",
    )


@router.delete("/{category_id}/share")
async def unshare_category(category_id: int, request: Request, db: Session = Depends(get_db)):
    """Zruší zdieľanie — existujúci link prestane fungovať (už importované kópie
    zostávajú, sú to samostatné sady)."""
    user = _get_current_user(request, db)
    category = (
        db.query(Category)
        .filter(Category.id == category_id, Category.user_id == user.id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    category.share_code = None
    db.commit()
    return {"message": "Sharing disabled"}


@router.get("/shared/{share_code}", response_model=SharedCategoryPreview)
async def shared_category_preview(share_code: str, db: Session = Depends(get_db)):
    """Verejný náhľad zdieľanej sady (bez prihlásenia) — pre landing /s/{kód}.

    Vracia len meno, popis, počet slov a jazyky — nie samotné slovíčka ani
    identitu vlastníka."""
    code = share_code.strip().upper()
    category = db.query(Category).filter(Category.share_code == code).first()
    if not category:
        raise HTTPException(
            status_code=404,
            detail="Zdieľaná sada neexistuje alebo bolo zdieľanie zrušené.",
        )

    total_words = (
        db.query(func.count(Word.id)).filter(Word.category_id == category.id).scalar() or 0
    )
    first_word = db.query(Word).filter(Word.category_id == category.id).first()

    return SharedCategoryPreview(
        share_code=code,
        name=category.name,
        description=category.description,
        total_words=total_words,
        language_from=first_word.language_from if first_word else None,
        language_to=first_word.language_to if first_word else None,
    )


@router.post("/import-shared", response_model=SharedCategoryImportResponse)
async def import_shared_category(
    payload: SharedCategoryImportRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Skopíruje zdieľanú sadu do účtu prihláseného používateľa (copy-on-import).

    Kópia príde celá aj nad WORD_LIMIT_FREE — limit slov platí pre vlastnú
    tvorbu, nie pre import (rovnaká logika ako XLSX import). Do limitu
    kategórií sa ale počíta, inak by si free účty preposielaním obišli limit.
    Štatistiky učenia sa nekopírujú — príjemca začína od nuly."""
    user = _get_current_user(request, db)

    code = payload.share_code.strip().upper()
    source = db.query(Category).filter(Category.share_code == code).first()
    if not source:
        raise HTTPException(
            status_code=404,
            detail="Zdieľaná sada neexistuje alebo bolo zdieľanie zrušené.",
        )
    if source.user_id == user.id:
        raise HTTPException(status_code=400, detail="Toto je vaša vlastná sada.")

    category_count = db.query(Category).filter(Category.user_id == user.id).count()
    limit = _get_category_limit(user)
    if limit is not None and category_count >= limit:
        raise HTTPException(
            status_code=400,
            detail=f"Dosiahli ste maximum {limit} kategórií. Aktivujte PLUS pre neobmedzené kategórie.",
        )

    # Meno musí byť per-user unikátne — pri kolízii pridaj číselný sufix.
    name = source.name
    suffix = 2
    while (
        db.query(Category)
        .filter(Category.name == name, Category.user_id == user.id)
        .first()
    ):
        if suffix > 50:
            raise HTTPException(status_code=400, detail="Túto sadu už máte importovanú.")
        name = f"{source.name} ({suffix})"
        suffix += 1

    new_category = Category(name=name, description=source.description, user_id=user.id)
    db.add(new_category)
    db.commit()
    db.refresh(new_category)

    source_words = db.query(Word).filter(Word.category_id == source.id).all()
    for w in source_words:
        db.add(
            Word(
                original_word=w.original_word,
                translation=w.translation,
                language_from=w.language_from,
                language_to=w.language_to,
                category_id=new_category.id,
                user_id=user.id,
            )
        )
    db.commit()

    return SharedCategoryImportResponse(
        category_id=new_category.id,
        category_name=name,
        imported_words=len(source_words),
    )


@router.post("/ai-create", response_model=AICategoryCreateResponse)
@limiter.limit("10/hour")
async def ai_create_category_and_words(
    ai_data: AICategoryCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_current_user(request, db)

    # Skontroluj limit PRED volanim AI (setri API credits)
    category_count = db.query(Category).filter(Category.user_id == user.id).count()
    limit = _get_category_limit(user)
    if limit is not None and category_count >= limit:
        raise HTTPException(
            status_code=400,
            detail=f"Dosiahli ste maximum {limit} kategórií. Aktivujte PLUS pre neobmedzené kategórie.",
        )

    chain = _provider_chain(ai_data.ai_provider)
    if not chain:
        raise HTTPException(
            status_code=500, detail="AI provider nie je nakonfigurovaný (chýba API kľúč)."
        )

    # Denný AI limit (Free účet) — započítaj pred volaním AI
    consume_ai_quota(db, user)

    generated = None
    rate_limited = False
    for provider in chain:
        try:
            if provider == "claude":
                generated = await generate_category_and_words_claude(
                    api_key=os.getenv("ANTHROPIC_API_KEY"),
                    model=os.getenv("CLAUDE_MODEL", "claude-opus-4-8"),
                    prompt=ai_data.prompt,
                    language_from=ai_data.language_from,
                    language_to=ai_data.language_to,
                    count=ai_data.count,
                )
            elif provider == "groq":
                generated = await generate_category_and_words_groq(
                    api_key=os.getenv("GROQ_API_KEY"),
                    model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                    prompt=ai_data.prompt,
                    language_from=ai_data.language_from,
                    language_to=ai_data.language_to,
                    count=ai_data.count,
                )
            else:
                generated = await generate_category_and_words_gemini(
                    api_key=os.getenv("GEMINI_API_KEY"),
                    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                    prompt=ai_data.prompt,
                    language_from=ai_data.language_from,
                    language_to=ai_data.language_to,
                    count=ai_data.count,
                )
            break
        except GeminiRateLimited:
            # Vyčerpaná kvóta nie je chyba kódu — stačí warning a ďalší provider.
            rate_limited = True
            logger.warning("AI category generation rate-limited (provider=%s)", provider)
        except Exception:
            logger.exception("AI category generation failed (provider=%s)", provider)

    if generated is None:
        # Neúspešný pokus nesmie Free účtu ukrojiť z denného AI limitu.
        refund_ai_quota(db, user)
        if rate_limited:
            raise HTTPException(
                status_code=429,
                detail="Denná kvóta AI je vyčerpaná. Skúste to prosím neskôr.",
            )
        raise HTTPException(
            status_code=502,
            detail="AI generovanie zlyhalo. Skúste to znova, prípadne znížte počet slov.",
        )

    return _persist_generated_category(
        db, user, generated, ai_data.language_from, ai_data.language_to, word_limit_for(user)
    )


@router.post("/ai-create-from-image", response_model=AICategoryCreateResponse)
@limiter.limit("10/hour")
async def ai_create_category_from_image(
    request: Request,
    image: UploadFile = File(...),
    language_from: str = Form("en"),
    language_to: str = Form("sk"),
    ai_provider: str = Form("gemini"),
    db: Session = Depends(get_db),
):
    """Vytvorí kategóriu zo slovíčok rozpoznaných na nahranej fotke/screenshote (AI vision)."""
    user = _get_current_user(request, db)

    # Limit kategórií skontroluj PRED volaním AI (šetri API credits)
    category_count = db.query(Category).filter(Category.user_id == user.id).count()
    limit = _get_category_limit(user)
    if limit is not None and category_count >= limit:
        raise HTTPException(
            status_code=400,
            detail=f"Dosiahli ste maximum {limit} kategórií. Aktivujte PLUS pre neobmedzené kategórie.",
        )

    media_type = (image.content_type or "").split(";")[0].strip().lower()
    if media_type not in IMAGE_ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Nepodporovaný formát obrázka. Povolené: PNG, JPG, WEBP, GIF.",
        )

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Prázdny súbor.")
    if len(image_bytes) > IMAGE_MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Obrázok je príliš veľký (max {IMAGE_MAX_BYTES // (1024 * 1024)} MB).",
        )

    # Over konfiguráciu PRED započítaním kvóty (aby chýbajúci API kľúč
    # nezožral používateľovi denný AI limit).
    chain = _provider_chain(ai_provider)
    if not chain:
        raise HTTPException(
            status_code=500, detail="AI provider nie je nakonfigurovaný (chýba API kľúč)."
        )

    # Denný AI limit (Free účet) — započítaj až po overení konfigurácie providera
    consume_ai_quota(db, user)

    image_b64 = base64.b64encode(image_bytes).decode("ascii")

    generated = None
    rate_limited = False
    for provider in chain:
        try:
            if provider == "claude":
                generated = await generate_category_and_words_from_image_claude(
                    api_key=os.getenv("ANTHROPIC_API_KEY"),
                    model=os.getenv("CLAUDE_MODEL", "claude-opus-4-8"),
                    image_b64=image_b64,
                    media_type=media_type,
                    language_from=language_from,
                    language_to=language_to,
                    max_count=IMAGE_MAX_WORDS,
                )
            elif provider == "groq":
                generated = await generate_category_and_words_from_image_groq(
                    api_key=os.getenv("GROQ_API_KEY"),
                    model=os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.6-27b"),
                    image_b64=image_b64,
                    media_type=media_type,
                    language_from=language_from,
                    language_to=language_to,
                    max_count=IMAGE_MAX_WORDS,
                )
            else:
                generated = await generate_category_and_words_from_image_gemini(
                    api_key=os.getenv("GEMINI_API_KEY"),
                    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                    image_b64=image_b64,
                    media_type=media_type,
                    language_from=language_from,
                    language_to=language_to,
                    max_count=IMAGE_MAX_WORDS,
                )
            break
        except GeminiRateLimited:
            rate_limited = True
            logger.warning("AI image category generation rate-limited (provider=%s)", provider)
        except Exception:
            logger.exception("AI image category generation failed (provider=%s)", provider)

    if generated is None:
        # Neúspešný pokus nesmie Free účtu ukrojiť z denného AI limitu.
        refund_ai_quota(db, user)
        if rate_limited:
            raise HTTPException(
                status_code=429,
                detail="Denná kvóta AI je vyčerpaná. Skúste to prosím neskôr.",
            )
        raise HTTPException(
            status_code=502,
            detail="AI generovanie z fotky zlyhalo. Skúste to znova s menšou/ostrejšou fotkou.",
        )

    return _persist_generated_category(
        db, user, generated, language_from, language_to, word_limit_for(user)
    )


@router.post("/ai-create-from-video", response_model=AICategoryCreateResponse)
@limiter.limit("5/hour")
async def ai_create_category_from_video(
    request: Request,
    ai_data: AICategoryFromVideoRequest,
    db: Session = Depends(get_db),
):
    """Vytvorí kategóriu zo slovíčok vo verejnom YouTube videu (AI).

    Len pre PLUS: video je najdrahšia AI operácia a na rozdiel od promptu
    a fotky nemá fallback na iného providera (YouTube URL vie spracovať
    jedine Gemini), takže jedno dlhé video vie vyčerpať dennú kvótu projektu."""
    user = _get_current_user(request, db)

    if not user.is_plus:
        raise HTTPException(
            status_code=403,
            detail="Generovanie z videa je dostupné len s PLUS predplatným.",
        )

    if not os.getenv("GEMINI_API_KEY"):
        raise HTTPException(
            status_code=500, detail="AI provider nie je nakonfigurovaný (chýba API kľúč)."
        )

    # Limit kategórií skontroluj PRED volaním AI (šetri API credits)
    category_count = db.query(Category).filter(Category.user_id == user.id).count()
    limit = _get_category_limit(user)
    if limit is not None and category_count >= limit:
        raise HTTPException(
            status_code=400,
            detail=f"Dosiahli ste maximum {limit} kategórií. Aktivujte PLUS pre neobmedzené kategórie.",
        )

    # Verejnosť + dĺžku over PRED volaním Gemini — zlé video tak neminie kvótu.
    try:
        video_id, video_title = await validate_youtube_url(ai_data.video_url)
    except YouTubeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    consume_ai_quota(db, user)

    try:
        generated = await generate_category_and_words_from_video_gemini(
            api_key=os.getenv("GEMINI_API_KEY"),
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            video_url=canonical_watch_url(video_id),
            video_title=video_title,
            language_from=ai_data.language_from,
            language_to=ai_data.language_to,
            max_count=VIDEO_MAX_WORDS,
        )
    except GeminiRateLimited:
        logger.warning("AI video category generation hit Gemini quota")
        refund_ai_quota(db, user)
        raise HTTPException(
            status_code=429,
            detail="Denná kvóta AI je vyčerpaná. Skúste to prosím neskôr.",
        )
    except Exception:
        logger.exception("AI video category generation failed (video_id=%s)", video_id)
        refund_ai_quota(db, user)
        raise HTTPException(
            status_code=502,
            detail="AI generovanie z videa zlyhalo. Skúste to znova, prípadne s kratším videom.",
        )

    return _persist_generated_category(
        db, user, generated, ai_data.language_from, ai_data.language_to, word_limit_for(user)
    )


@router.get("/{category_id}/stats")
async def get_category_stats(category_id: int, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)

    category = (
        db.query(Category)
        .filter(Category.id == category_id, Category.user_id == user.id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    summary = get_category_word_summary(db, user.id, [category_id])[category_id]
    total_words = summary["total_words"]
    level_counts = summary["level_counts"]

    stats = {
        "total_words": total_words,
        "dont_know_percentage": round((level_counts.get("dont_know", 0) / total_words * 100), 1)
        if total_words > 0
        else 0,
        "learning_percentage": round((level_counts.get("learning", 0) / total_words * 100), 1)
        if total_words > 0
        else 0,
        "know_percentage": round((level_counts.get("know", 0) / total_words * 100), 1)
        if total_words > 0
        else 0,
    }
    return JSONResponse(stats)
