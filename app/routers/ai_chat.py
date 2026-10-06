"""Rozhovor s AI nad slovíčkami sady.

Dva endpointy: `start` vyberie slovíčka, odpočíta jedno AI generovanie a vráti
prvú otázku; `reply` pokračuje. Server si rozhovor nepamätá (žiadna tabuľka,
žiadna migrácia) — klient posiela históriu a podpísaný lístok zo `start`,
z ktorého server vie, ktoré slová a úroveň do rozhovoru patria.
"""
import os
import random

from fastapi import APIRouter, Depends, HTTPException, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.word import KnowledgeLevel, Word
from app.routers.categories import AI_PROVIDER_KEYS, _provider_chain
from app.schemas.ai_chat import (
    ChatReplyRequest,
    ChatReplyResponse,
    ChatStartRequest,
    ChatStartResponse,
)
from app.services.ai_category_service import GeminiRateLimited
from app.services.ai_chat_service import (
    CHAT_MAX_USER_MESSAGES,
    CHAT_MESSAGE_MAX_LENGTH,
    CHAT_WORDS,
    generate_chat_reply,
)
from app.services.limits import consume_ai_quota, refund_ai_quota
from app.services.runtime import SECRET_KEY, limiter, logger
from app.services.session_auth import get_authenticated_user

router = APIRouter(prefix="/api/v1/categories", tags=["ai-chat"])

# Ako dlho sa dá v začatom rozhovore pokračovať. Po uplynutí treba začať nový
# (a ten stojí ďalšie AI generovanie) — lístok tak nie je trvalá vstupenka.
CHAT_TOKEN_MAX_AGE_S = 2 * 60 * 60

_signer = URLSafeTimedSerializer(SECRET_KEY, salt="ai-chat")

_EXPIRED = "Rozhovor vypršal. Začni prosím nový."


def _word_rows(db: Session, user_id: int, category_id: int, word_ids=None) -> list:
    """Slovíčka sady ako obyčajné riadky. Len vlastné sady: sada triedy patrí
    učiteľovi a jej žiaci môžu byť deti — rozhovor s AI im zatiaľ neponúkame."""
    query = db.query(
        Word.id, Word.original_word, Word.translation,
        Word.language_from, Word.language_to, Word.knowledge_level,
    ).filter(Word.category_id == category_id, Word.user_id == user_id)
    if word_ids is not None:
        query = query.filter(Word.id.in_(word_ids))
    return query.all()


def _pick_words(rows: list) -> list:
    """Najprv slová, ktoré používateľ ešte nevie, potom doplniť zvládnutými;
    z oboch náhodne, aby každý rozhovor bol o inej desiatke."""
    unknown = [r for r in rows if r.knowledge_level != KnowledgeLevel.KNOW]
    known = [r for r in rows if r.knowledge_level == KnowledgeLevel.KNOW]
    random.shuffle(unknown)
    random.shuffle(known)
    return (unknown + known)[:CHAT_WORDS]


async def _ask_ai(words: list, level: str, messages: list) -> str:
    """Odpoveď AI podľa reťazca providerov; chyby mapuje na 429/502."""
    rate_limited = False
    for provider in _provider_chain("gemini"):
        try:
            return await generate_chat_reply(
                provider=provider,
                api_key=os.getenv(AI_PROVIDER_KEYS[provider]),
                model=(
                    os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
                    if provider == "groq"
                    else os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                ),
                words=[{"original_word": w.original_word, "translation": w.translation} for w in words],
                level=level,
                language_from=words[0].language_from or "en",
                language_to=words[0].language_to or "sk",
                messages=messages,
            )
        except GeminiRateLimited:
            rate_limited = True
            logger.warning("AI chat rate-limited (provider=%s)", provider)
        except Exception:
            logger.exception("AI chat failed (provider=%s)", provider)

    if rate_limited:
        raise HTTPException(status_code=429, detail="AI je práve vyťažená. Skús to prosím o chvíľu.")
    raise HTTPException(status_code=502, detail="AI neodpovedala. Skús to prosím znova.")


@router.post("/{category_id}/chat/start", response_model=ChatStartResponse)
@limiter.limit("10/hour")
async def start_chat(
    category_id: int,
    payload: ChatStartRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Začne rozhovor: vyberie slovíčka a vráti prvú otázku AI.

    Stojí jedno AI generovanie z denného limitu (pri zlyhaní AI sa vráti);
    pokračovanie cez `reply` už limit neodpočítava.
    """
    user = get_authenticated_user(request, db)

    rows = _word_rows(db, user.id, category_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Sada neexistuje alebo nemá žiadne slovíčka.")
    words = _pick_words(rows)

    if not _provider_chain("gemini"):
        raise HTTPException(
            status_code=500, detail="AI provider nie je nakonfigurovaný (chýba API kľúč)."
        )

    # `consume_ai_quota` commituje — id používateľa si treba vziať pred ním,
    # inak by ho po commite ORM dočítavalo ďalším dotazom.
    user_id = user.id
    consume_ai_quota(db, user)
    try:
        reply = await _ask_ai(words, payload.level, [])
    except HTTPException:
        refund_ai_quota(db, user)
        raise

    token = _signer.dumps({
        "u": user_id, "c": category_id, "l": payload.level, "w": [w.id for w in words],
    })
    return ChatStartResponse(
        token=token,
        words=[{"original_word": w.original_word, "translation": w.translation} for w in words],
        reply=reply,
        messages_left=CHAT_MAX_USER_MESSAGES,
    )


@router.post("/{category_id}/chat/reply", response_model=ChatReplyResponse)
@limiter.limit("120/hour")
async def reply_chat(
    category_id: int,
    payload: ChatReplyRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Pokračuje v rozhovore: dostane celú históriu, vráti ďalšiu správu AI."""
    user = get_authenticated_user(request, db)

    try:
        ticket = _signer.loads(payload.token, max_age=CHAT_TOKEN_MAX_AGE_S)
    except BadSignature:   # zahŕňa aj vypršaný lístok (SignatureExpired)
        raise HTTPException(status_code=400, detail=_EXPIRED)
    if ticket.get("u") != user.id or ticket.get("c") != category_id:
        raise HTTPException(status_code=400, detail=_EXPIRED)

    # História sa strieda AI → používateľ a končí správou používateľa.
    for index, message in enumerate(payload.messages):
        expected = "assistant" if index % 2 == 0 else "user"
        if message.role != expected:
            raise HTTPException(status_code=400, detail="Neplatná história rozhovoru.")
        if message.role == "user" and len(message.text.strip()) > CHAT_MESSAGE_MAX_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"Správa je príliš dlhá (najviac {CHAT_MESSAGE_MAX_LENGTH} znakov).",
            )
    if payload.messages[-1].role != "user":
        raise HTTPException(status_code=400, detail="Neplatná história rozhovoru.")
    user_messages = len(payload.messages) // 2
    if user_messages > CHAT_MAX_USER_MESSAGES:
        raise HTTPException(status_code=400, detail="Rozhovor je na konci. Začni prosím nový.")

    by_id = {row.id: row for row in _word_rows(db, user.id, category_id, ticket.get("w") or [])}
    words = [by_id[word_id] for word_id in ticket.get("w") or [] if word_id in by_id]
    if not words:
        raise HTTPException(
            status_code=400, detail="Slovíčka z tohto rozhovoru už v sade nie sú. Začni prosím nový."
        )

    reply = await _ask_ai(
        words, ticket.get("l"),
        [{"role": m.role, "text": m.text.strip()} for m in payload.messages],
    )
    return ChatReplyResponse(reply=reply, messages_left=CHAT_MAX_USER_MESSAGES - user_messages)
