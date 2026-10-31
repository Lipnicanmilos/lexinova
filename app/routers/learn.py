"""Jedno učenie (`/ucenie`): dávka slov s úlohami. Výsledky idú cez `/test/submit`
rovnako ako z testu, takže streak, graf aj priehradky sa rátajú na jednom mieste."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.schemas.word import LearnItem
from app.services.learning import build_session
from app.services.session_auth import get_authenticated_user

router = APIRouter(prefix="/api/v1/learn", tags=["learn"])


@router.get("/session", response_model=List[LearnItem])
def learn_session(
    category_id: Optional[int] = Query(None, description="Len jedna sada; inak výber naprieč sadami"),
    extra: bool = Query(False, description="Učenie navyše, bez ohľadu na termín"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    return build_session(db, current_user, category_id=category_id, extra=extra)
