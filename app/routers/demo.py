"""Verejný endpoint pre ukážku na /demo — jediné AI volanie bez prihlásenia.

Ochrany sú tri a každá rieši inú vec:
  * `@limiter.limit` — jeden návštevník (IP) nespotrebuje viac než pár volaní,
  * cache podľa témy — opakovaná téma nestojí nič,
  * denný strop naprieč všetkými — po vyčerpaní sa podáva uložená sada.

Nič sa neukladá k žiadnemu účtu a nevzniká kategória: výsledok existuje len
v prehliadači návštevníka. Uložiť si ho môže až po registrácii.
"""
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.services import demo_service
from app.services.ai_category_service import (
    GeminiRateLimited,
    generate_category_and_words_gemini,
    generate_category_and_words_groq,
)
from app.services.runtime import limiter, logger

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


class DemoGenerateRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=demo_service.TOPIC_MAX_LENGTH)
    language_from: str = Field(default="en", max_length=10)
    language_to: str = Field(default="sk", max_length=10)


class DemoWord(BaseModel):
    original: str
    translation: str


class DemoGenerateResponse(BaseModel):
    topic: str
    category_name: str | None = None
    language_from: str
    language_to: str
    words: list[DemoWord]
    # ai = práve vygenerované, cache = rovnakú tému už niekto zadal,
    # sample = denný strop je vyčerpaný, ukazujeme pripravenú sadu.
    source: str
    requested_topic: str


@router.post("/generate", response_model=DemoGenerateResponse)
@limiter.limit("5/hour")
async def demo_generate(
    payload: DemoGenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    topic = payload.topic.strip()
    topic_key = demo_service.normalize_topic(topic)
    if not topic_key:
        # Samé interpunkčné znaky — po normalizácii by z témy nezostalo nič.
        raise HTTPException(status_code=400, detail="Zadaj tému slovami, napríklad: cestovanie lietadlom.")

    language_from = payload.language_from.strip().lower() or "en"
    language_to = payload.language_to.strip().lower() or "sk"

    cached = demo_service.find_cached(db, topic_key, language_from, language_to)
    if cached:
        return {**cached, "requested_topic": topic}

    if demo_service.budget_left(db) <= 0:
        logger.info("Demo: denny strop AI volani vycerpany, podavam ulozenu sadu")
        return {**demo_service.fallback_set(db, language_from, language_to), "requested_topic": topic}

    generated = await _generate(topic, language_from, language_to)
    if generated is None:
        # Zlyhanie AI nesmie byť pre návštevníka slepá ulička — ukážka je jediné
        # miesto, kde sa rozhoduje, či si vôbec založí účet.
        return {**demo_service.fallback_set(db, language_from, language_to), "requested_topic": topic}

    words = demo_service.normalize_words(generated.get("words"))
    if not words:
        return {**demo_service.fallback_set(db, language_from, language_to), "requested_topic": topic}

    words = words[:demo_service.DEMO_WORD_COUNT]
    category_name = generated.get("category_name")
    demo_service.store_generated(
        db, topic=topic, topic_key=topic_key, language_from=language_from,
        language_to=language_to, category_name=category_name, words=words,
    )
    return {
        "topic": topic,
        "category_name": category_name,
        "language_from": language_from,
        "language_to": language_to,
        "words": words,
        "source": "ai",
        "requested_topic": topic,
    }


async def _generate(topic: str, language_from: str, language_to: str):
    """Gemini, pri zlyhaní Groq. Claude sa v ukážke nepoužíva — je platený.

    Vracia payload alebo None; volajúci má pripravenú náhradnú sadu, takže sa
    tu nič nevyhadzuje.
    """
    providers = [
        ("gemini", "GEMINI_API_KEY", generate_category_and_words_gemini, "GEMINI_MODEL", "gemini-2.5-flash"),
        ("groq", "GROQ_API_KEY", generate_category_and_words_groq, "GROQ_MODEL", "llama-3.3-70b-versatile"),
    ]
    for name, key_env, func, model_env, model_default in providers:
        api_key = os.getenv(key_env)
        if not api_key:
            continue
        try:
            return await func(
                api_key=api_key,
                model=os.getenv(model_env, model_default),
                prompt=topic,
                language_from=language_from,
                language_to=language_to,
                count=demo_service.DEMO_WORD_COUNT,
            )
        except GeminiRateLimited:
            logger.warning("Demo: %s hlasi vycerpanu kvotu, skusam dalsieho", name)
        except Exception:
            logger.exception("Demo: generovanie zlyhalo (provider=%s)", name)
    return None
