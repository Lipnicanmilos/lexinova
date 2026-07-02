from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User


def get_session_user(request: Request) -> dict:
    user_session = request.session.get("user")
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_session


def get_authenticated_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    user_session = get_session_user(request)
    user = db.query(User).filter(User.id == user_session["id"]).first()
    if not user:
        # Session ukazuje na zmazaný účet — z pohľadu klienta nie je prihlásený.
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
