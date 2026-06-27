from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, constr
from sqlalchemy import func
from sqlalchemy.exc import ProgrammingError, OperationalError, IntegrityError
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.inquiry import Inquiry
from app.models.user import User
from app.services.email_service import send_inquiry_notification
from app.services.session_auth import get_authenticated_user
from app.services.runtime import ADMIN_EMAILS, limiter

router = APIRouter(tags=["inquiry"])


class InquiryCreate(BaseModel):
    name: str | None = None
    email: str | None = None
    message: constr(strip_whitespace=True, min_length=2, max_length=4000)
    page: str | None = None


def _require_admin(current_user: User):
    if not getattr(current_user, "email", None):
        raise HTTPException(status_code=403, detail="Admin access denied")
    email = current_user.email.lower().strip()
    if ADMIN_EMAILS and email in ADMIN_EMAILS:
        return
    raise HTTPException(status_code=403, detail="Admin access denied")


# ── VEREJNÝ ENDPOINT – odoslanie dotazu (bez prihlásenia) ──
@router.post("/api/inquiry")
@limiter.limit("5/hour")
async def create_inquiry(
    payload: InquiryCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    ua = request.headers.get("user-agent", "")[:400]

    inquiry = Inquiry(
        name=(payload.name or "").strip()[:120] or None,
        email=(payload.email or "").strip()[:255] or None,
        message=payload.message.strip(),
        page=(payload.page or "").strip()[:255] or None,
        user_agent=ua,
        is_read=False,
    )
    try:
        db.add(inquiry)
        db.commit()
        db.refresh(inquiry)
    except (ProgrammingError, OperationalError):
        db.rollback()
        raise HTTPException(status_code=503, detail="Inquiry service temporarily unavailable")

    # E-mail notifikácia (neblokuje uloženie ak zlyhá)
    send_inquiry_notification(
        name=inquiry.name or "",
        email=inquiry.email or "",
        message=inquiry.message,
        page=inquiry.page or "",
    )

    return JSONResponse({"ok": True, "id": inquiry.id})


# ── ADMIN – zoznam dotazov ──
@router.get("/api/admin/inquiries")
async def admin_inquiries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    _require_admin(current_user)

    try:
        rows = db.query(Inquiry).order_by(Inquiry.created_at.desc()).limit(300).all()
        total = db.query(func.count(Inquiry.id)).scalar() or 0
        unread = db.query(func.count(Inquiry.id)).filter(Inquiry.is_read.is_(False)).scalar() or 0
    except (ProgrammingError, OperationalError):
        db.rollback()
        return JSONResponse({"enabled": False, "stats": {}, "inquiries": []})

    return JSONResponse(
        {
            "enabled": True,
            "stats": {"total": int(total), "unread": int(unread)},
            "inquiries": [
                {
                    "id": r.id,
                    "name": r.name,
                    "email": r.email,
                    "message": r.message,
                    "page": r.page,
                    "is_read": bool(r.is_read),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ],
        }
    )


# ── ADMIN – označiť ako prečítané / neprečítané ──
@router.patch("/api/admin/inquiries/{inquiry_id}")
async def admin_mark_inquiry(
    inquiry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    _require_admin(current_user)
    inquiry = db.query(Inquiry).filter(Inquiry.id == inquiry_id).first()
    if not inquiry:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    inquiry.is_read = not bool(inquiry.is_read)
    db.commit()
    db.refresh(inquiry)
    return JSONResponse({"id": inquiry.id, "is_read": bool(inquiry.is_read)})


# ── ADMIN – zmazať dotaz ──
@router.delete("/api/admin/inquiries/{inquiry_id}")
async def admin_delete_inquiry(
    inquiry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    _require_admin(current_user)
    inquiry = db.query(Inquiry).filter(Inquiry.id == inquiry_id).first()
    if not inquiry:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    db.delete(inquiry)
    db.commit()
    return JSONResponse({"deleted_inquiry_id": inquiry_id})
