# app/schemas/school_class.py — Triedy (Fáza 2 učiteľského kanála)
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel


class ClassCreate(BaseModel):
    name: str


class ClassRename(BaseModel):
    name: str


class ClassJoin(BaseModel):
    """Pridanie prihláseného (e-mailového) usera do triedy."""
    class_code: str
    nickname: Optional[str] = None


class ClassJoinNew(BaseModel):
    """Pseudonymná registrácia žiaka: kód triedy + prezývka + heslo (bez e-mailu)."""
    class_code: str
    nickname: str
    password: str


class ClassLogin(BaseModel):
    class_code: str
    nickname: str
    password: str


class MemberPasswordReset(BaseModel):
    new_password: str


class ClassAssignCategory(BaseModel):
    category_id: int


class ClassResponse(BaseModel):
    id: int
    name: str
    join_code: str
    join_url: str
    member_count: int = 0
    category_count: int = 0
    created_at: Optional[datetime] = None


class ClassMemberResponse(BaseModel):
    id: int  # id členstva (nie usera)
    nickname: str
    is_pseudonymous: bool
    joined_at: Optional[datetime] = None


class ClassPreview(BaseModel):
    """Verejný náhľad triedy pre landing /c/{kód} — bez zoznamu žiakov."""
    class_code: str
    name: str
    teacher_name: Optional[str] = None
    member_count: int = 0


class MyClassResponse(BaseModel):
    class_id: int
    class_name: str
    teacher_name: Optional[str] = None
    nickname: str


class ClassOverviewMember(BaseModel):
    member_id: int
    nickname: str
    is_pseudonymous: bool
    joined_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    tests_taken: int = 0
    success_rate: Optional[float] = None  # % zo súčtov TestSession na sadách triedy
    mastery: Dict[int, Dict[str, int]] = {}  # category_id -> level_counts


class ClassOverviewCategory(BaseModel):
    id: int
    name: str
    total_words: int = 0


class ClassOverviewResponse(BaseModel):
    class_id: int
    class_name: str
    categories: List[ClassOverviewCategory] = []
    members: List[ClassOverviewMember] = []
