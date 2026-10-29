"""AI tútor s pamäťou (/tutor) — API.

- `GET  /api/v1/tutor/state`                  — prístup, profil, rozbehnutá relácia, zostatok správ
- `POST /api/v1/tutor/sessions`               — nová relácia (staršie nezhrnuté najprv zhrnie), pozdrav tútora
- `POST /api/v1/tutor/sessions/{id}/messages` — správa používateľa → odpoveď tútora
- `POST /api/v1/tutor/sessions/{id}/end`      — zhrnutie relácie do pamäte + nové slovíčka do sady
- `POST /api/v1/tutor/transcribe`             — nahrávka reči → text a rozpoznaný jazyk (Whisper)
- `DELETE /api/v1/tutor/memory`               — zabudni všetko (profil, relácie, spomienky)

Relácia môže bežať nad vlastnou sadou (`category_id` pri štarte): vybrané
slovíčka sa uložia ako riadok `role="focus"` v `tutor_messages` — patria
k relácii, netreba na ne nový stĺpec ani migráciu. Do histórie sa nepočítajú.

Prístup: PLUS alebo admin, nikdy pseudonymný (žiacky) účet — žiaci môžu byť
deti a tútor si o človeku ukladá osobné údaje. Rozhovor ide zo spoločnej
(bezplatnej) kvóty Gemini, preto má každý používateľ denný strop správ a relácia
vlastný strop.
"""
import asyncio
import json
import os
from datetime import datetime, time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.category import Category
from app.models.tutor import TutorMemory, TutorMessage, TutorProfile, TutorSession
from app.models.user import User
from app.models.word import KnowledgeLevel, Word
from app.routers.ai_chat import _pick_words, _word_rows
from app.schemas.tutor import (
    TutorEndResponse,
    TutorMessageRequest,
    TutorMessageResponse,
    TutorStartRequest,
    TutorStartResponse,
)
from app.services import tutor_service as svc
from app.services.ai_category_service import GeminiRateLimited
from app.services.runtime import ADMIN_EMAILS, limiter, logger
from app.services.session_auth import get_authenticated_user
from app.services.word_dedupe import headword_key, merge_translations
from app.utils import utcnow

router = APIRouter(prefix="/api/v1/tutor", tags=["tutor"])

TUTOR_DAILY_MESSAGES_DEFAULT = 100
TUTOR_SESSION_MAX_USER_MESSAGES = 60
TUTOR_CATEGORY_NAME = "AI tútor"

_ENDED = "Táto relácia už skončila. Začni prosím novú."
_BUSY = "AI tútor je práve vyťažený. Skús to prosím o chvíľu."


def daily_message_limit() -> int:
    try:
        return max(1, int(os.getenv("TUTOR_DAILY_MESSAGES", TUTOR_DAILY_MESSAGES_DEFAULT)))
    except ValueError:
        return TUTOR_DAILY_MESSAGES_DEFAULT


def _is_admin(user: User) -> bool:
    return bool(ADMIN_EMAILS) and (user.email or "").lower().strip() in ADMIN_EMAILS


def access_problem(user: User) -> Optional[str]:
    """None = smie; inak dôvod, prečo nie (text pre používateľa)."""
    if user.is_pseudonymous:
        return "AI tútor nie je dostupný pre žiacke účty."
    if not (user.is_plus or _is_admin(user)):
        return "AI tútor s pamäťou je súčasťou PLUS."
    if not svc.is_configured():
        return "AI tútor nie je nakonfigurovaný (chýba API kľúč pre AI)."
    return None


def _require_access(user: User) -> None:
    problem = access_problem(user)
    if problem:
        status = 503 if "nakonfigurovaný" in problem else 403
        raise HTTPException(status_code=status, detail=problem)


def _messages_today(db: Session, user_id: int) -> int:
    midnight = datetime.combine(utcnow().date(), time.min)
    return (
        db.query(TutorMessage)
        .filter(TutorMessage.user_id == user_id, TutorMessage.role == "user",
                TutorMessage.created_at >= midnight)
        .count()
    )


def _get_profile(db: Session, user_id: int) -> TutorProfile:
    profile = db.get(TutorProfile, user_id)
    if profile is None:
        profile = TutorProfile(user_id=user_id, level="A2", language_from="en", language_to="sk",
                               sessions_count=0)
        db.add(profile)
        db.commit()
    return profile


FOCUS_ROLE = "focus"


def _history(db: Session, session_id: int, limit: Optional[int] = None) -> List[dict]:
    query = db.query(TutorMessage).filter(
        TutorMessage.session_id == session_id, TutorMessage.role != FOCUS_ROLE
    )
    if limit:
        rows = query.order_by(TutorMessage.created_at.desc(), TutorMessage.id.desc()).limit(limit).all()
        rows.reverse()
    else:
        rows = query.order_by(TutorMessage.created_at, TutorMessage.id).all()
    return [{"role": m.role, "text": m.text} for m in rows]


def _focus(db: Session, session_id: int) -> Optional[dict]:
    """Slovíčka sady, nad ktorou relácia beží, alebo None."""
    row = (
        db.query(TutorMessage.text)
        .filter(TutorMessage.session_id == session_id, TutorMessage.role == FOCUS_ROLE)
        .first()
    )
    if row is None:
        return None
    try:
        data = json.loads(row.text)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _set_focus(db: Session, user_id: int, category_id: int) -> dict:
    """Vyberie slovíčka vlastnej sady do relácie. Sada triedy ani cudzia sada
    nejde (žiaci môžu byť deti) — rovnako ako rozhovor s AI na stránke sady."""
    rows = _word_rows(db, user_id, category_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Sada neexistuje alebo nemá žiadne slovíčka.")
    name = db.query(Category.name).filter(Category.id == category_id).scalar()
    words = _pick_words(rows)
    return {
        "category_id": category_id,
        "name": name or "",
        "language_from": (words[0].language_from or "").lower(),
        "words": [{"word": w.original_word, "translation": w.translation} for w in words],
    }


def _owned_session(db: Session, user_id: int, session_id: int) -> TutorSession:
    session = db.get(TutorSession, session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(status_code=404, detail="Relácia neexistuje.")
    return session


def _add_words(db: Session, user_id: int, profile: TutorProfile, words: List[dict]) -> int:
    """Nové slovíčka z relácie do sady „AI tútor" — opakujú sa potom ako
    každá iná sada. Rovnaké heslo sa nepridá druhýkrát, len sa doplní preklad."""
    if not words:
        return 0
    category = (
        db.query(Category)
        .filter(Category.user_id == user_id, Category.name == TUTOR_CATEGORY_NAME)
        .first()
    )
    if category is None:
        category = Category(
            name=TUTOR_CATEGORY_NAME, user_id=user_id,
            description="Slovíčka, ktoré ti chýbali v rozhovoroch s AI tútorom.",
        )
        db.add(category)
        db.flush()

    existing = {
        headword_key(w.original_word): w
        for w in db.query(Word).filter(Word.category_id == category.id).all()
    }
    added = 0
    for item in words:
        key = headword_key(item["word"])
        if key in existing:
            merged = merge_translations(existing[key].translation, item["translation"])
            if merged:
                existing[key].translation = merged
            continue
        word = Word(
            original_word=item["word"], translation=item["translation"],
            language_from=profile.language_from, language_to=profile.language_to,
            category_id=category.id, user_id=user_id,
            knowledge_level=KnowledgeLevel.DONT_KNOW,
        )
        db.add(word)
        existing[key] = word
        added += 1
    return added


async def finalize_session(db: Session, session: TutorSession, profile: TutorProfile) -> dict:
    """Zhrnie reláciu do pamäte. Vyhodí výnimku, ak AI zlyhá — relácia potom
    ostane otvorená a dá sa zhrnúť znova."""
    history = _history(db, session.id)
    if session.user_messages <= 0 or not any(m["role"] == "user" for m in history):
        # Len pozdrav, používateľ nič nenapísal — nie je čo pamätať.
        session.ended_at = utcnow()
        db.commit()
        return {"summary": None, "words_added": 0, "level": profile.level}

    data = await svc.summarize_session(profile=profile, history=history)

    summary = " ".join(data["summary"].split())[:1000]
    facts = svc.as_bullets(data.get("facts"), max_items=25)
    mistakes = svc.as_bullets(data.get("mistakes"), max_items=12)
    new_facts = [f for f in (data.get("new_facts") or []) if isinstance(f, str) and f.strip()][:10]
    level = data.get("level") if data.get("level") in svc.TUTOR_LEVELS else profile.level

    texts = [summary] + [" ".join(f.split())[:200] for f in new_facts]
    vectors = await asyncio.gather(*(svc.embed_text(t) for t in texts))

    db.add(TutorMemory(user_id=session.user_id, session_id=session.id, kind="summary",
                       text=summary, embedding=vectors[0]))
    for fact_text, vector in zip(texts[1:], vectors[1:]):
        db.add(TutorMemory(user_id=session.user_id, session_id=session.id, kind="fact",
                           text=fact_text, embedding=vector))

    if facts:
        profile.facts = facts
    if mistakes:
        profile.mistakes = mistakes
    profile.level = level
    profile.sessions_count = (profile.sessions_count or 0) + 1
    session.summary = summary
    session.ended_at = utcnow()

    words_added = _add_words(db, session.user_id, profile, svc.clean_new_words(data.get("new_words")))
    db.commit()
    return {"summary": summary, "words_added": words_added, "level": level}


@router.get("/state")
async def tutor_state(request: Request, set: Optional[int] = None, db: Session = Depends(get_db)):
    """`set` = id sady, zo stránky ktorej používateľ prišiel — vráti jej názov,
    aby stránka vedela ponúknuť rozhovor nad ňou."""
    user = get_authenticated_user(request, db)
    problem = access_problem(user)
    if problem:
        return {"available": False, "reason": problem}

    user_id = user.id
    try:
        profile = _get_profile(db, user_id)
        session = svc.active_session(db, user_id)
        used = _messages_today(db, user_id)
    except (ProgrammingError, OperationalError):
        db.rollback()
        logger.exception("Tutor tables missing — run migrations/2026-10-28_tutor_memory.sql")
        return {"available": False, "reason": "AI tútor ešte nie je pripravený (chýba migrácia databázy)."}

    return {
        "available": True,
        "profile": {
            "level": profile.level,
            "language_from": profile.language_from,
            "language_to": profile.language_to,
            "facts": profile.facts,
            "mistakes": profile.mistakes,
            "sessions_count": profile.sessions_count or 0,
        },
        "session": None if session is None else {
            "id": session.id,
            "messages": _history(db, session.id),
            "messages_left": max(0, TUTOR_SESSION_MAX_USER_MESSAGES - (session.user_messages or 0)),
            "focus": _focus(db, session.id),
        },
        "set": _set_info(db, user_id, set) if set else None,
        "messages_left_today": max(0, daily_message_limit() - used),
    }


def _set_info(db: Session, user_id: int, category_id: int) -> Optional[dict]:
    """Názov vlastnej sady (cudzia či sada triedy → None)."""
    name = (
        db.query(Category.name)
        .filter(Category.id == category_id, Category.user_id == user_id)
        .scalar()
    )
    return None if name is None else {"id": category_id, "name": name}


@router.post("/sessions", response_model=TutorStartResponse)
@limiter.limit("20/hour")
async def start_session(payload: TutorStartRequest, request: Request, db: Session = Depends(get_db)):
    user = get_authenticated_user(request, db)
    _require_access(user)
    user_id = user.id

    focus = _set_focus(db, user_id, payload.category_id) if payload.category_id else None

    profile = _get_profile(db, user_id)
    if payload.level:
        profile.level = payload.level
    if focus and focus["language_from"] in svc.TUTOR_LANGUAGES:
        # Rozhovor nad sadou je v jazyku jej slovíčok, nech si zvolil čokoľvek.
        profile.language_from = focus["language_from"]
    elif payload.language_from:
        profile.language_from = payload.language_from
    db.commit()

    # Relácie, ktoré používateľ len zavrel, zhrnieme teraz — inak by sa ich obsah
    # do pamäte nikdy nedostal. Zlyhanie AI tu nesmie zablokovať novú reláciu:
    # takú reláciu uzavrieme bez súhrnu, aby sa neplatilo za ňu dookola.
    for old in db.query(TutorSession).filter(
        TutorSession.user_id == user_id, TutorSession.ended_at.is_(None)
    ).all():
        try:
            await finalize_session(db, old, profile)
        except Exception:
            db.rollback()
            logger.exception("Tutor: finalizing old session %s failed", old.id)
            old.ended_at = utcnow()
            db.commit()

    instructions = svc.build_instructions(profile, focus)
    notes = svc.build_memory_notes(profile, svc.recent_summaries(db, user_id), [])
    try:
        reply = await svc.generate_reply(instructions=instructions, notes=notes, history=[])
    except GeminiRateLimited:
        raise HTTPException(status_code=429, detail=_BUSY)
    except Exception:
        logger.exception("Tutor: greeting failed")
        raise HTTPException(status_code=502, detail="AI tútor neodpovedal. Skús to prosím znova.")

    session = TutorSession(user_id=user_id, started_at=utcnow(), user_messages=0)
    db.add(session)
    db.flush()
    now = utcnow()
    if focus:
        focus_json = json.dumps({k: focus[k] for k in ("category_id", "name", "words")}, ensure_ascii=False)
        db.add(TutorMessage(session_id=session.id, user_id=user_id, role=FOCUS_ROLE,
                            text=focus_json, created_at=now))
    db.add(TutorMessage(session_id=session.id, user_id=user_id, role="assistant", text=reply, created_at=now))
    db.commit()

    return TutorStartResponse(
        session_id=session.id,
        reply=reply,
        level=profile.level,
        language_from=profile.language_from,
        messages_left=TUTOR_SESSION_MAX_USER_MESSAGES,
        messages_left_today=max(0, daily_message_limit() - _messages_today(db, user_id)),
        focus=None if not focus else {k: focus[k] for k in ("category_id", "name", "words")},
    )


@router.post("/sessions/{session_id}/messages", response_model=TutorMessageResponse)
@limiter.limit("200/hour")
async def send_message(
    session_id: int, payload: TutorMessageRequest, request: Request, db: Session = Depends(get_db)
):
    user = get_authenticated_user(request, db)
    _require_access(user)
    user_id = user.id

    session = _owned_session(db, user_id, session_id)
    if session.ended_at is not None:
        raise HTTPException(status_code=400, detail=_ENDED)
    if (session.user_messages or 0) >= TUTOR_SESSION_MAX_USER_MESSAGES:
        raise HTTPException(status_code=400, detail="Relácia je na konci. Ukonči ju a začni novú.")
    used = _messages_today(db, user_id)
    if used >= daily_message_limit():
        raise HTTPException(status_code=429, detail="Na dnes je limit správ vyčerpaný. Pokračujme zajtra.")

    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Správa je prázdna.")
    if len(text) > svc.TUTOR_MESSAGE_MAX_LENGTH:
        raise HTTPException(
            status_code=400, detail=f"Správa je príliš dlhá (najviac {svc.TUTOR_MESSAGE_MAX_LENGTH} znakov)."
        )

    profile = _get_profile(db, user_id)
    history = _history(db, session.id, limit=svc.TUTOR_HISTORY_MESSAGES) + [{"role": "user", "text": text}]

    summaries = svc.recent_summaries(db, user_id)
    query_vector = await svc.embed_text(text, task="RETRIEVAL_QUERY")
    relevant = svc.find_relevant_memories(db, user_id, query_vector, exclude_ids={m.id for m in summaries})

    try:
        reply = await svc.generate_reply(
            instructions=svc.build_instructions(profile, _focus(db, session.id)),
            notes=svc.build_memory_notes(profile, summaries, relevant),
            history=history,
        )
    except GeminiRateLimited:
        raise HTTPException(status_code=429, detail=_BUSY)
    except Exception:
        logger.exception("Tutor: reply failed (session %s)", session_id)
        raise HTTPException(status_code=502, detail="AI tútor neodpovedal. Skús to prosím znova.")

    # Obe správy sa ukladajú až po úspešnej odpovedi — pri zlyhaní AI v histórii
    # neostane otázka bez odpovede a správa sa nezapočíta do limitu.
    now = utcnow()
    db.add(TutorMessage(session_id=session.id, user_id=user_id, role="user", text=text, created_at=now))
    db.add(TutorMessage(session_id=session.id, user_id=user_id, role="assistant", text=reply, created_at=now))
    session.user_messages = (session.user_messages or 0) + 1
    db.commit()

    parts = svc.split_reply(reply)
    return TutorMessageResponse(
        reply=parts["reply"],
        correction=parts["correction"],
        help=parts["help"],
        messages_left=max(0, TUTOR_SESSION_MAX_USER_MESSAGES - session.user_messages),
        messages_left_today=max(0, daily_message_limit() - used - 1),
    )


@router.post("/sessions/{session_id}/end", response_model=TutorEndResponse)
@limiter.limit("30/hour")
async def end_session(session_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_authenticated_user(request, db)
    _require_access(user)
    user_id = user.id

    session = _owned_session(db, user_id, session_id)
    if session.ended_at is not None:
        return TutorEndResponse(summary=session.summary, words_added=0, already_ended=True)

    profile = _get_profile(db, user_id)
    try:
        result = await finalize_session(db, session, profile)
    except GeminiRateLimited:
        db.rollback()
        raise HTTPException(status_code=429, detail=_BUSY)
    except Exception:
        db.rollback()
        logger.exception("Tutor: summary failed (session %s)", session_id)
        raise HTTPException(status_code=502, detail="Zhrnutie sa nepodarilo. Skús to prosím znova.")
    return TutorEndResponse(summary=result["summary"], words_added=result["words_added"],
                            level=result["level"])


@router.post("/transcribe")
@limiter.limit("150/hour")
async def transcribe(request: Request, db: Session = Depends(get_db)):
    """Nahrávka reči (telo požiadavky, `Content-Type: audio/...`) → `{text, language}`.

    Prepis robí Whisper (Groq), ktorý sám rozpozná jazyk — používateľ tak môže
    tútorovi hovoriť po anglicky aj po slovensky bez prepínania. Funguje v každom
    prehliadači s MediaRecorderom, aj vo Firefoxe. Nahrávku neukladáme."""
    user = get_authenticated_user(request, db)
    _require_access(user)

    mime = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if mime not in svc.AUDIO_MIME_EXT:
        raise HTTPException(status_code=415, detail="Nepodporovaný formát nahrávky.")
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > svc.TUTOR_AUDIO_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Nahrávka je príliš dlhá.")
    # Telo čítame po kúskoch so stropom — Content-Length sa dá vynechať.
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > svc.TUTOR_AUDIO_MAX_BYTES:
            raise HTTPException(status_code=413, detail="Nahrávka je príliš dlhá.")
    if not data:
        raise HTTPException(status_code=400, detail="Nahrávka je prázdna.")
    if not svc.can_transcribe():
        raise HTTPException(status_code=503, detail="Prepis reči nie je nakonfigurovaný.")

    try:
        result = await svc.transcribe_audio(bytes(data), mime)
    except GeminiRateLimited:
        raise HTTPException(status_code=429, detail=_BUSY)
    except Exception:
        logger.exception("Tutor: transcription failed")
        raise HTTPException(status_code=502, detail="Reč sa nepodarilo prepísať. Skús to prosím znova.")
    return {"text": result["text"][: svc.TUTOR_MESSAGE_MAX_LENGTH], "language": result["language"]}


def delete_tutor_data(db: Session, user_id: int) -> None:
    """Zmaže všetko, čo si tútor o používateľovi pamätá. Volá sa aj pri zmazaní
    účtu (v PG by to spravila FK kaskáda, v SQLite testoch nie)."""
    db.query(TutorMemory).filter(TutorMemory.user_id == user_id).delete(synchronize_session=False)
    db.query(TutorMessage).filter(TutorMessage.user_id == user_id).delete(synchronize_session=False)
    db.query(TutorSession).filter(TutorSession.user_id == user_id).delete(synchronize_session=False)
    db.query(TutorProfile).filter(TutorProfile.user_id == user_id).delete(synchronize_session=False)


@router.delete("/memory")
@limiter.limit("10/hour")
async def forget_everything(request: Request, db: Session = Depends(get_db)):
    """Zabudni všetko. Sada „AI tútor" so slovíčkami ostáva — je to bežná sada
    používateľa a zmazať si ju môže sám."""
    user = get_authenticated_user(request, db)
    delete_tutor_data(db, user.id)
    db.commit()
    return {"message": "Tútor zabudol všetko, čo si o tebe pamätal."}
