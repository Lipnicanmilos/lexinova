from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.models.word import Word
from app.models.category import Category
from app.services.session_auth import get_authenticated_user
from app.services.runtime import ADMIN_EMAILS

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



@router.get("/admin")
async def admin_page(
    request: Request,
    current_user: User = Depends(get_authenticated_user),
):
    _require_admin(current_user)
    # Render HTML admin template
    from app.services.runtime import templates

    return templates.TemplateResponse("admin.html", {"request": request, "email": current_user.email})



@router.get("/api/admin/users")
async def admin_users(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    _require_admin(current_user)

    # words_count + categories_count + last_login
    users = db.query(
        User.id,
        User.email,
        User.is_plus,
        User.last_login,
        func.count(Category.id).label("categories_count"),
        func.count(Word.id).label("words_count"),
    ).outerjoin(Category, Category.user_id == User.id) \
     .outerjoin(Word, Word.user_id == User.id) \
     .group_by(User.id, User.email, User.is_plus, User.last_login) \
     .all()

    total_words_all_users = (
        db.query(func.coalesce(func.sum(Word.id), 0)).scalar() or 0
    )

    return JSONResponse(
        {
            "total_users": len(users),
            "total_words_all_users": total_words_all_users,
            "users": [
                {
                    "id": u.id,
                    "email": u.email,
                    "is_plus": bool(u.is_plus),
                    "last_login": u.last_login.isoformat() if u.last_login else None,
                    "categories_count": int(u.categories_count or 0),
                    "words_count": int(u.words_count or 0),
                }
                for u in users
            ],
        }
    )

