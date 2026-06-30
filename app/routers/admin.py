from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_
from sqlalchemy.exc import ProgrammingError, OperationalError
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.models.word import Word
from app.models.category import Category
from app.models.test_session import TestSession
from app.schemas.user import UserUpdate, PlusGrant
from app.services.session_auth import get_authenticated_user
from app.services.runtime import ADMIN_EMAILS
from app.services.billing_service import (
    ACTIVE_STATUSES,
    PAYING_STATUSES,
    PRICE_MONTHLY_EUR,
    PRICE_ANNUAL_EUR,
)
from app.utils import utcnow

# Payment je optional – ak by sa model ešte nedeployol, admin nespadne.
try:
    from app.models.payment import Payment
    _HAS_PAYMENT = True
except Exception:  # pragma: no cover
    Payment = None
    _HAS_PAYMENT = False

router = APIRouter(tags=["admin"])


def _require_admin(current_user: User):
    # Admin autorizácia cez allow-list emailov z ENV
    # ADMIN_EMAILS=mail1@gmail.com,mail2@gmail.com
    if not getattr(current_user, "email", None):
        raise HTTPException(status_code=403, detail="Admin access denied")

    email = current_user.email.lower().strip()
    if ADMIN_EMAILS and email in ADMIN_EMAILS:
        return

    # Ak ADMIN_EMAILS nie je nastavené, admin nikto nemá.
    raise HTTPException(status_code=403, detail="Admin access denied")


def _extended_expiry(current, days, now):
    """Posunie expiráciu o ``days`` (kladné predĺži, záporné skráti). Ak PLUS
    ešte platí, naviaže sa na koniec aktuálneho obdobia (nepremrhá zostávajúce
    dni), inak počíta od ``now``."""
    base = current if (current and current > now) else now
    return base + timedelta(days=days)


def _mrr(monthly_count, annual_count):
    """Mesačný opakovaný príjem (EUR) z počtu platiacich mesačných/ročných predplatných."""
    return round(monthly_count * PRICE_MONTHLY_EUR + annual_count * (PRICE_ANNUAL_EUR / 12.0), 2)


@router.get("/admin")
async def admin_page(
    request: Request,
    current_user: User = Depends(get_authenticated_user),
):
    _require_admin(current_user)
    from app.services.runtime import templates
    return templates.TemplateResponse(request, "admin.html", {"email": current_user.email})


@router.get("/api/admin/users")
async def admin_users(
    request: Request,
    q: str = "",
    plus: str = "all",            # all | plus | standard
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    _require_admin(current_user)

    # Poddotazy aby sa counts nenásobili joinmi
    categories_subq = (
        db.query(
            Category.user_id.label("user_id"),
            func.count(Category.id).label("categories_count"),
        )
        .group_by(Category.user_id)
        .subquery()
    )

    words_subq = (
        db.query(
            Word.user_id.label("user_id"),
            func.count(Word.id).label("words_count"),
        )
        .group_by(Word.user_id)
        .subquery()
    )

    query = (
        db.query(
            User.id,
            User.email,
            User.name,
            User.is_plus,
            User.plus_plan,
            User.plus_status,
            User.plus_expires_at,
            User.plus_cancelled_at,
            User.created_at,
            User.last_login,
            func.coalesce(categories_subq.c.categories_count, 0).label("categories_count"),
            func.coalesce(words_subq.c.words_count, 0).label("words_count"),
        )
        .outerjoin(categories_subq, categories_subq.c.user_id == User.id)
        .outerjoin(words_subq, words_subq.c.user_id == User.id)
    )

    # Vyhľadávanie podľa emailu / mena
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(User.email.ilike(like), User.name.ilike(like)))

    # Filter Plus / Standard
    if plus == "plus":
        query = query.filter(User.is_plus.is_(True))
    elif plus == "standard":
        query = query.filter(or_(User.is_plus.is_(False), User.is_plus.is_(None)))

    users = query.order_by(User.id).all()

    # Globálne štatistiky (nezávislé na filtri)
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_plus = db.query(func.count(User.id)).filter(User.is_plus.is_(True)).scalar() or 0
    total_words_all_users = db.query(func.count(Word.id)).scalar() or 0
    total_categories_all = db.query(func.count(Category.id)).scalar() or 0

    # Noví používatelia za posledných 7 / 30 dní
    now = datetime.now(timezone.utc)
    new_7d = (
        db.query(func.count(User.id))
        .filter(User.created_at >= now - timedelta(days=7))
        .scalar()
        or 0
    )
    new_30d = (
        db.query(func.count(User.id))
        .filter(User.created_at >= now - timedelta(days=30))
        .scalar()
        or 0
    )

    return JSONResponse(
        {
            "stats": {
                "total_users": int(total_users),
                "total_plus": int(total_plus),
                "total_standard": int(total_users - total_plus),
                "total_words_all_users": int(total_words_all_users),
                "total_categories_all": int(total_categories_all),
                "new_users_7d": int(new_7d),
                "new_users_30d": int(new_30d),
            },
            "count": len(users),
            "users": [
                {
                    "id": u.id,
                    "email": u.email,
                    "name": u.name,
                    "is_plus": bool(u.is_plus),
                    "plus_plan": u.plus_plan,
                    "plus_status": u.plus_status,
                    "plus_expires_at": u.plus_expires_at.isoformat() if u.plus_expires_at else None,
                    "plus_cancelled_at": u.plus_cancelled_at.isoformat() if u.plus_cancelled_at else None,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                    "last_login": u.last_login.isoformat() if u.last_login else None,
                    "categories_count": int(u.categories_count or 0),
                    "words_count": int(u.words_count or 0),
                }
                for u in users
            ],
        }
    )


@router.patch("/api/admin/users/{user_id}")
async def admin_update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    _require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.email is not None:
        new_email = payload.email.strip()
        existing = db.query(User).filter(User.email == new_email, User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = new_email

    if payload.is_plus is not None:
        user.is_plus = bool(payload.is_plus)

    db.commit()
    db.refresh(user)

    return JSONResponse({"id": user.id, "email": user.email, "is_plus": bool(user.is_plus)})


@router.post("/api/admin/users/{user_id}/grant-plus")
async def admin_grant_plus(
    user_id: int,
    payload: PlusGrant,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Manuálny admin grant PLUS o N dní (override bez platby).

    Kladné ``days`` predĺžia, záporné skrátia ``plus_expires_at`` (od konca
    aktuálneho obdobia, ak ešte platí). Reálny plán (monthly/annual z Paddle)
    sa zachová; pri ručnom grante bez plánu sa nastaví 'admin' (nevstupuje do
    MRR). Ak skrátenie posunie expiráciu do minulosti, PLUS sa vypne."""
    _require_admin(current_user)

    days = payload.days
    if days == 0 or days < -3650 or days > 3650:
        raise HTTPException(status_code=400, detail="Počet dní musí byť −3650 až 3650 (≠ 0)")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = utcnow()
    new_expiry = _extended_expiry(user.plus_expires_at, days, now)
    user.plus_expires_at = new_expiry

    if new_expiry > now:
        user.is_plus = True
        user.plus_status = "active"
        user.plus_plan = user.plus_plan or "admin"
        user.plus_cancelled_at = None
    else:
        # Skrátenie posunulo expiráciu do minulosti → PLUS končí.
        user.is_plus = False
        user.plus_status = "expired"

    db.commit()
    db.refresh(user)

    return JSONResponse(
        {
            "id": user.id,
            "email": user.email,
            "is_plus": bool(user.is_plus),
            "plus_expires_at": user.plus_expires_at.isoformat() if user.plus_expires_at else None,
            "granted_days": days,
        }
    )


@router.post("/api/admin/users/{user_id}/revoke-plus")
async def admin_revoke_plus(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Okamžite zruší PLUS (admin override) — vypne prístup teraz.

    Vyčistí expiráciu a nastaví status 'expired'. Paddle ID-čka a plán ostávajú
    ako história (do MRR nevstupujú, lebo is_plus=False)."""
    _require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_plus = False
    user.plus_status = "expired"
    user.plus_expires_at = None
    user.plus_cancelled_at = None

    db.commit()
    db.refresh(user)

    return JSONResponse(
        {"id": user.id, "email": user.email, "is_plus": bool(user.is_plus)}
    )


@router.delete("/api/admin/users/{user_id}")
async def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    _require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Admin nesmie zmazať sám seba (poistka)
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own admin account")

    # Word.user_id nemá FK constraint -> mazať explicitne.
    # Poradie: test_sessions -> words -> categories -> user (kvôli FK na categories/users).
    try:
        db.query(TestSession).filter(TestSession.user_id == user_id).delete(synchronize_session=False)
    except (ProgrammingError, OperationalError):
        db.rollback()
    deleted_words = db.query(Word).filter(Word.user_id == user_id).delete(synchronize_session=False)
    deleted_categories = (
        db.query(Category).filter(Category.user_id == user_id).delete(synchronize_session=False)
    )
    db.delete(user)
    db.commit()

    return JSONResponse(
        {
            "deleted_user_id": user_id,
            "deleted_words": int(deleted_words or 0),
            "deleted_categories": int(deleted_categories or 0),
        }
    )


@router.get("/api/admin/logs")
async def admin_logs(
    request: Request,
    lines: int = 300,
    level: str = "",          # "", INFO, WARNING, ERROR, CRITICAL, DEBUG
    q: str = "",              # textové vyhľadávanie (substring, case-insensitive)
    current_user: User = Depends(get_authenticated_user),
):
    _require_admin(current_user)

    import glob
    import os
    from collections import deque

    from app.services.runtime import LOG_FILE

    lines = max(1, min(lines, 2000))  # rozumný strop
    level = (level or "").strip().upper()
    q = (q or "").strip().lower()
    level_token = f" {level} " if level else ""

    # Rotované (staršie) najprv, aktuálny súbor (najnovší) nakoniec.
    rotated = sorted(glob.glob(LOG_FILE + ".*"))
    ordered = rotated + ([LOG_FILE] if os.path.exists(LOG_FILE) else [])

    if not ordered:
        return JSONResponse(
            {
                "available": False,
                "lines": [],
                "note": "Log súbor zatiaľ neexistuje (alebo beží read-only / čerstvá Cloud Run inštancia). Trvalé online logy nájdeš v Google Cloud Logging.",
            }
        )

    buf: deque = deque(maxlen=lines)
    for path in ordered:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.rstrip("\n")
                    if level_token and level_token not in line:
                        continue
                    if q and q not in line.lower():
                        continue
                    buf.append(line)
        except OSError:
            continue

    return JSONResponse(
        {"available": True, "count": len(buf), "lines": list(buf), "filtered": bool(level or q)}
    )


@router.get("/api/admin/payments")
async def admin_payments(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    _require_admin(current_user)

    # Predplatné + MRR sa počítajú z User tabuľky (nezávisle od Payment tabuľky).
    def _count_plan(plan, statuses):
        return (
            db.query(func.count(User.id))
            .filter(
                User.is_plus.is_(True),
                User.plus_plan == plan,
                User.plus_status.in_(statuses),
            )
            .scalar()
            or 0
        )

    monthly_active = int(_count_plan("monthly", tuple(ACTIVE_STATUSES)))
    annual_active = int(_count_plan("annual", tuple(ACTIVE_STATUSES)))
    monthly_paying = int(_count_plan("monthly", tuple(PAYING_STATUSES)))
    annual_paying = int(_count_plan("annual", tuple(PAYING_STATUSES)))
    mrr = _mrr(monthly_paying, annual_paying)
    subscriptions = {
        "active_subscriptions": monthly_active + annual_active,
        "monthly_active": monthly_active,
        "annual_active": annual_active,
        "mrr": mrr,
        "arr": round(mrr * 12, 2),
    }

    if not _HAS_PAYMENT:
        return JSONResponse(
            {"enabled": False, "subscriptions": subscriptions, "stats": {}, "payments": []}
        )

    try:
        rows = db.query(Payment).order_by(Payment.created_at.desc()).limit(100).all()

        # Súhrny len cez úspešné platby
        succeeded = db.query(Payment).filter(Payment.status == "succeeded")
        total_revenue = succeeded.with_entities(func.coalesce(func.sum(Payment.amount), 0.0)).scalar() or 0.0
        total_count = succeeded.count()

        now = datetime.now(timezone.utc)
        rev_30d = (
            db.query(func.coalesce(func.sum(Payment.amount), 0.0))
            .filter(Payment.status == "succeeded", Payment.created_at >= now - timedelta(days=30))
            .scalar()
            or 0.0
        )
    except (ProgrammingError, OperationalError):
        # Tabuľka payments ešte neexistuje v DB (nebol spustený create_all migrácia)
        db.rollback()
        return JSONResponse(
            {"enabled": False, "subscriptions": subscriptions, "stats": {}, "payments": []}
        )

    return JSONResponse(
        {
            "enabled": True,
            "subscriptions": subscriptions,
            "stats": {
                "total_revenue": round(float(total_revenue), 2),
                "succeeded_count": int(total_count),
                "revenue_30d": round(float(rev_30d), 2),
            },
            "payments": [
                {
                    "id": p.id,
                    "email": p.email,
                    "user_id": p.user_id,
                    "provider": p.provider,
                    "status": p.status,
                    "amount": float(p.amount or 0.0),
                    "currency": p.currency,
                    "description": p.description,
                    "subscription_id": p.provider_subscription_id,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in rows
            ],
        }
    )
