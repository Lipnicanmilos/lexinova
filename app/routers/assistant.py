"""Pokyny pre Lexi — `POST /api/v1/assistant/command`.

Pokyn → akcia (`assistant_service`). Prístup rovnaký ako AI tútor: PLUS alebo
admin, nikdy žiacky účet. Endpoint nič nevytvára: pri `create_set` vráti zadanie
pre `/categories/ai-preview`, sada sa uloží až po potvrdení cez `/ai-save`.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.category import Category
from app.routers.tutor import _require_access
from app.services import assistant_service
from app.services.ai_category_service import GeminiRateLimited
from app.services.runtime import limiter, logger
from app.services.session_auth import get_authenticated_user

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])

COMMAND_MAX_LENGTH = 500
_BUSY = "Lexi je práve vyťažená (bezplatná kvóta AI sa minula). Skús to prosím o chvíľu."


class AssistantCommand(BaseModel):
    text: str = Field(min_length=1, max_length=COMMAND_MAX_LENGTH * 2)
    ui_lang: Literal["sk", "en"] = "sk"


@router.post("/command")
@limiter.limit("60/hour")
async def command(payload: AssistantCommand, request: Request, db: Session = Depends(get_db)):
    user = get_authenticated_user(request, db)
    _require_access(user)

    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Pokyn je prázdny.")
    if len(text) > COMMAND_MAX_LENGTH:
        raise HTTPException(status_code=400, detail=f"Pokyn je príliš dlhý (najviac {COMMAND_MAX_LENGTH} znakov).")

    # Len vlastné sady (nie sady triedy) — tie si používateľ môže precvičiť aj rozprávať sa nad nimi.
    rows = (
        db.query(Category.id, Category.name)
        .filter(Category.user_id == user.id)
        .order_by(Category.id.desc())
        .limit(assistant_service.SETS_IN_PROMPT)
        .all()
    )
    sets = [{"id": r.id, "name": r.name} for r in rows]

    try:
        return await assistant_service.interpret(text, sets, payload.ui_lang)
    except GeminiRateLimited:
        raise HTTPException(status_code=429, detail=_BUSY)
    except Exception:
        logger.exception("Assistant: command failed")
        raise HTTPException(status_code=502, detail="Lexi teraz nerozumie. Skús to prosím znova.")
