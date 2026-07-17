"""Prístup k triednym sadám (Fáza 2 učiteľského kanála).

Sady triedy sú live odkaz na učiteľove kategórie — žiak k nim má čítací
prístup cez členstvo v triede a jeho pokrok sa ukladá do word_progress
(nie na učiteľove Word riadky).
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.school_class import ClassCategory, ClassMember
from app.models.user import User
from app.models.word_progress import WordProgress


def is_class_member_category(db: Session, user_id: int, category_id: int) -> bool:
    """True, ak má user prístup ku kategórii ako člen triedy, ktorej je priradená."""
    return (
        db.query(ClassMember.id)
        .join(ClassCategory, ClassCategory.class_id == ClassMember.class_id)
        .filter(
            ClassMember.user_id == user_id,
            ClassCategory.category_id == category_id,
        )
        .first()
        is not None
    )


def get_class_category_for_member(db: Session, user: User, category_id: int) -> Optional[Category]:
    """Vráti CUDZIU kategóriu, ku ktorej má user prístup cez triedu, inak None.

    Vlastné kategórie vracia None — tie idú existujúcou (nezmenenou) cestou.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category or category.user_id == user.id:
        return None
    if not is_class_member_category(db, user.id, category_id):
        return None
    return category


def get_progress_map(db: Session, user_id: int, word_ids: list[int]) -> dict[int, WordProgress]:
    """Mapa word_id -> WordProgress daného usera (chýbajúci záznam = netestované)."""
    if not word_ids:
        return {}
    rows = (
        db.query(WordProgress)
        .filter(WordProgress.user_id == user_id, WordProgress.word_id.in_(word_ids))
        .all()
    )
    return {progress.word_id: progress for progress in rows}
