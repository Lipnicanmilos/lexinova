"""Triedy (Fáza 2 učiteľského kanála).

Učiteľ (PLUS) založí triedu, žiaci sa pridajú kódom triedy — buď existujúcim
účtom, alebo pseudonymne (prezývka + heslo, bez e-mailu; GDPR čl. 8).
Sady priradené triede vidia žiaci live a nepočítajú sa im do limitov.

PLUS gating: založenie triedy a prehľad žiakov = PLUS. Po vypršaní PLUS
učiteľa trieda ďalej žije (žiaci sa učia, join funguje, správa členov ide),
zablokované je len zakladanie nových tried a prehľad.
"""
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.category import Category
from app.models.school_class import ClassCategory, ClassMember, SchoolClass
from app.models.test_session import TestSession
from app.models.user import User
from app.models.word import Word
from app.models.word_progress import WordProgress
from app.routers.auth import _TIMING_DUMMY_HASH, password_strength_error
from app.schemas.school_class import (
    ClassAssignCategory,
    ClassCreate,
    ClassJoin,
    ClassJoinNew,
    ClassLogin,
    ClassMemberResponse,
    ClassOverviewCategory,
    ClassOverviewMember,
    ClassOverviewResponse,
    ClassPreview,
    ClassRename,
    ClassResponse,
    MemberPasswordReset,
    MyClassResponse,
)
from app.services.auth_service import hash_password, verify_password
from app.services.runtime import limiter, logger
from app.services.session_auth import get_authenticated_user
from app.utils import utcnow

router = APIRouter(prefix="/api/v1/classes", tags=["classes"])

# Rovnaká abeceda ako share kódy (bez O/0, I/1/L — diktovateľné v triede),
# ale kratší kód: deti ho píšu ručne. 31^6 ≈ 887 mil. kombinácií.
JOIN_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
JOIN_CODE_LENGTH = 6
SITE_URL = os.getenv("SITE_URL", "https://lexinova.fun").rstrip("/")

NICKNAME_MIN = 2
NICKNAME_MAX = 30

PLUS_REQUIRED_DETAIL = "Triedy sú dostupné len s PLUS predplatným."
INVALID_CLASS_LOGIN = "Nesprávny kód triedy, prezývka alebo heslo."


def _generate_join_code(db: Session) -> str:
    for _ in range(5):
        code = "".join(secrets.choice(JOIN_CODE_ALPHABET) for _ in range(JOIN_CODE_LENGTH))
        if not db.query(SchoolClass).filter(SchoolClass.join_code == code).first():
            return code
    raise HTTPException(status_code=500, detail="Nepodarilo sa vygenerovať kód triedy.")


def _normalize_code(code: str) -> str:
    return (code or "").strip().upper()


def _clean_nickname(nickname: str) -> str:
    cleaned = " ".join((nickname or "").split())  # orezanie + zlúčenie medzier
    if not (NICKNAME_MIN <= len(cleaned) <= NICKNAME_MAX):
        raise HTTPException(
            status_code=400,
            detail=f"Prezývka musí mať {NICKNAME_MIN}–{NICKNAME_MAX} znakov.",
        )
    return cleaned


def _get_owned_class(db: Session, user: User, class_id: int) -> SchoolClass:
    school_class = (
        db.query(SchoolClass)
        .filter(SchoolClass.id == class_id, SchoolClass.teacher_id == user.id)
        .first()
    )
    if not school_class:
        raise HTTPException(status_code=404, detail="Trieda nenájdená.")
    return school_class


def _require_plus(user: User):
    if not user.is_plus:
        raise HTTPException(status_code=403, detail=PLUS_REQUIRED_DETAIL)


def _class_by_code(db: Session, class_code: str) -> SchoolClass:
    code = _normalize_code(class_code)
    school_class = db.query(SchoolClass).filter(SchoolClass.join_code == code).first()
    if not school_class:
        raise HTTPException(status_code=404, detail="Trieda s týmto kódom neexistuje.")
    return school_class


def _class_response(db: Session, school_class: SchoolClass) -> ClassResponse:
    member_count = (
        db.query(func.count(ClassMember.id))
        .filter(ClassMember.class_id == school_class.id)
        .scalar()
        or 0
    )
    category_ids = [
        row[0]
        for row in db.query(ClassCategory.category_id)
        .filter(ClassCategory.class_id == school_class.id)
        .all()
    ]
    return ClassResponse(
        id=school_class.id,
        name=school_class.name,
        join_code=school_class.join_code,
        join_url=f"{SITE_URL}/c/{school_class.join_code}",
        member_count=member_count,
        category_count=len(category_ids),
        category_ids=category_ids,
        created_at=school_class.created_at,
    )


def _set_session_user(request: Request, user: User):
    request.session["user"] = {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "is_plus": user.is_plus,
        "dark_mode": user.dark_mode,
    }


# ── Učiteľ ────────────────────────────────────────────────────────────────────

@router.post("", response_model=ClassResponse)
async def create_class(
    data: ClassCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    _require_plus(current_user)
    name = (data.name or "").strip()
    if not (1 <= len(name) <= 100):
        raise HTTPException(status_code=400, detail="Názov triedy musí mať 1–100 znakov.")

    school_class = SchoolClass(
        name=name,
        teacher_id=current_user.id,
        join_code=_generate_join_code(db),
    )
    db.add(school_class)
    db.commit()
    db.refresh(school_class)
    return _class_response(db, school_class)


@router.get("", response_model=list[ClassResponse])
async def list_my_classes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    # Bez PLUS gate — učiteľ s vypršaným PLUS musí vidieť a spravovať existujúce triedy.
    classes = (
        db.query(SchoolClass)
        .filter(SchoolClass.teacher_id == current_user.id)
        .order_by(SchoolClass.created_at)
        .all()
    )
    return [_class_response(db, c) for c in classes]


@router.put("/{class_id}", response_model=ClassResponse)
async def rename_class(
    class_id: int,
    data: ClassRename,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    school_class = _get_owned_class(db, current_user, class_id)
    name = (data.name or "").strip()
    if not (1 <= len(name) <= 100):
        raise HTTPException(status_code=400, detail="Názov triedy musí mať 1–100 znakov.")
    school_class.name = name
    db.commit()
    return _class_response(db, school_class)


@router.delete("/{class_id}")
async def delete_class(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    school_class = _get_owned_class(db, current_user, class_id)

    # Pseudonymní žiaci bez ďalšieho členstva by po zmazaní triedy ostali
    # navždy neprihlásiteľní (login = kód triedy) — zmažeme aj ich účty.
    member_rows = (
        db.query(ClassMember, User)
        .join(User, User.id == ClassMember.user_id)
        .filter(ClassMember.class_id == school_class.id)
        .all()
    )
    orphan_ids = []
    for member, user in member_rows:
        if not user.is_pseudonymous:
            continue
        other = (
            db.query(ClassMember.id)
            .filter(ClassMember.user_id == user.id, ClassMember.class_id != school_class.id)
            .first()
        )
        if not other:
            orphan_ids.append(user.id)

    db.delete(school_class)  # ORM kaskáda: members + category priradenia

    if orphan_ids:
        # Explicitne (nie FK kaskádou) — SQLite v testoch FK kaskády nevynucuje.
        db.query(TestSession).filter(TestSession.user_id.in_(orphan_ids)).delete(
            synchronize_session=False
        )
        db.query(WordProgress).filter(WordProgress.user_id.in_(orphan_ids)).delete(
            synchronize_session=False
        )
        # membershipy sirôt maže ORM kaskáda (delete triedy + delete usera)
        for orphan in db.query(User).filter(User.id.in_(orphan_ids)).all():
            db.delete(orphan)

    db.commit()
    logger.info(
        f"Class {class_id} deleted by user {current_user.id}, orphan pseudonymous accounts: {len(orphan_ids)}"
    )
    return JSONResponse({"message": "Trieda bola zmazaná.", "deleted_student_accounts": len(orphan_ids)})


@router.post("/{class_id}/regenerate-code", response_model=ClassResponse)
async def regenerate_join_code(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    school_class = _get_owned_class(db, current_user, class_id)
    school_class.join_code = _generate_join_code(db)
    db.commit()
    return _class_response(db, school_class)


@router.get("/{class_id}/members", response_model=list[ClassMemberResponse])
async def list_members(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    school_class = _get_owned_class(db, current_user, class_id)
    rows = (
        db.query(ClassMember, User)
        .join(User, User.id == ClassMember.user_id)
        .filter(ClassMember.class_id == school_class.id)
        .order_by(ClassMember.joined_at)
        .all()
    )
    return [
        ClassMemberResponse(
            id=member.id,
            nickname=member.nickname,
            is_pseudonymous=bool(user.is_pseudonymous),
            joined_at=member.joined_at,
        )
        for member, user in rows
    ]


@router.delete("/{class_id}/members/{member_id}")
async def remove_member(
    class_id: int,
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    school_class = _get_owned_class(db, current_user, class_id)
    member = (
        db.query(ClassMember)
        .filter(ClassMember.id == member_id, ClassMember.class_id == school_class.id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Člen nenájdený.")
    db.delete(member)
    db.commit()
    return JSONResponse({"message": "Člen bol odstránený z triedy."})


@router.post("/{class_id}/members/{member_id}/reset-password")
async def reset_member_password(
    class_id: int,
    member_id: int,
    data: MemberPasswordReset,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    school_class = _get_owned_class(db, current_user, class_id)
    row = (
        db.query(ClassMember, User)
        .join(User, User.id == ClassMember.user_id)
        .filter(ClassMember.id == member_id, ClassMember.class_id == school_class.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Člen nenájdený.")
    member, user = row
    # Zásadné: NIKDY nedovoliť učiteľovi resetnúť heslo e-mailového účtu.
    if not user.is_pseudonymous:
        raise HTTPException(
            status_code=403,
            detail="Heslo možno resetovať len žiackym (pseudonymným) kontám.",
        )
    error = password_strength_error(data.new_password)
    if error:
        raise HTTPException(status_code=400, detail=error)
    user.password = hash_password(data.new_password)
    db.commit()
    return JSONResponse({"message": f"Heslo pre '{member.nickname}' bolo zmenené."})


@router.post("/{class_id}/categories")
async def assign_category(
    class_id: int,
    data: ClassAssignCategory,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    school_class = _get_owned_class(db, current_user, class_id)
    category = (
        db.query(Category)
        .filter(Category.id == data.category_id, Category.user_id == current_user.id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Kategória nenájdená.")
    existing = (
        db.query(ClassCategory)
        .filter(
            ClassCategory.class_id == school_class.id,
            ClassCategory.category_id == category.id,
        )
        .first()
    )
    if existing:
        return JSONResponse({"message": "Sada už je triede priradená."})
    db.add(ClassCategory(class_id=school_class.id, category_id=category.id))
    db.commit()
    return JSONResponse({"message": f"Sada '{category.name}' bola priradená triede."})


@router.delete("/{class_id}/categories/{category_id}")
async def unassign_category(
    class_id: int,
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    school_class = _get_owned_class(db, current_user, class_id)
    deleted = (
        db.query(ClassCategory)
        .filter(
            ClassCategory.class_id == school_class.id,
            ClassCategory.category_id == category_id,
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Sada nie je triede priradená.")
    return JSONResponse({"message": "Sada bola odobraná triede."})


@router.get("/{class_id}/overview", response_model=ClassOverviewResponse)
async def class_overview(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    _require_plus(current_user)
    school_class = _get_owned_class(db, current_user, class_id)

    member_rows = (
        db.query(ClassMember, User)
        .join(User, User.id == ClassMember.user_id)
        .filter(ClassMember.class_id == school_class.id)
        .order_by(ClassMember.joined_at)
        .all()
    )
    assigned = (
        db.query(Category)
        .join(ClassCategory, ClassCategory.category_id == Category.id)
        .filter(ClassCategory.class_id == school_class.id)
        .all()
    )
    assigned_ids = [c.id for c in assigned]
    member_user_ids = [user.id for _, user in member_rows]

    totals = {}
    if assigned_ids:
        for category_id, count in (
            db.query(Word.category_id, func.count(Word.id))
            .filter(Word.category_id.in_(assigned_ids))
            .group_by(Word.category_id)
            .all()
        ):
            totals[category_id] = count

    # Aktivita a úspešnosť LEN nad sadami triedy (data minimization —
    # súkromné sady žiaka učiteľ nevidí).
    sessions = {}
    if assigned_ids and member_user_ids:
        for user_id, tests, total_sum, correct_sum, last_at in (
            db.query(
                TestSession.user_id,
                func.count(TestSession.id),
                func.sum(TestSession.total),
                func.sum(TestSession.correct),
                func.max(TestSession.created_at),
            )
            .filter(
                TestSession.user_id.in_(member_user_ids),
                TestSession.category_id.in_(assigned_ids),
            )
            .group_by(TestSession.user_id)
            .all()
        ):
            sessions[user_id] = (tests, total_sum or 0, correct_sum or 0, last_at)

    # Mastery per žiak per sada z word_progress (chýbajúci riadok = dont_know).
    progress = {}
    if assigned_ids and member_user_ids:
        for user_id, category_id, level, count in (
            db.query(
                WordProgress.user_id,
                Word.category_id,
                WordProgress.knowledge_level,
                func.count(WordProgress.id),
            )
            .join(Word, Word.id == WordProgress.word_id)
            .filter(
                WordProgress.user_id.in_(member_user_ids),
                Word.category_id.in_(assigned_ids),
            )
            .group_by(WordProgress.user_id, Word.category_id, WordProgress.knowledge_level)
            .all()
        ):
            level_value = level.value if hasattr(level, "value") else level
            progress.setdefault(user_id, {}).setdefault(category_id, {})[level_value] = count

    members = []
    for member, user in member_rows:
        tests, total_sum, correct_sum, last_at = sessions.get(user.id, (0, 0, 0, None))
        mastery = {}
        for category_id in assigned_ids:
            counts = dict(progress.get(user.id, {}).get(category_id, {}))
            counted = sum(counts.values())
            counts["dont_know"] = counts.get("dont_know", 0) + max(
                totals.get(category_id, 0) - counted, 0
            )
            counts.setdefault("learning", 0)
            counts.setdefault("know", 0)
            mastery[category_id] = counts
        members.append(
            ClassOverviewMember(
                member_id=member.id,
                nickname=member.nickname,
                is_pseudonymous=bool(user.is_pseudonymous),
                joined_at=member.joined_at,
                last_activity=last_at,
                tests_taken=tests,
                success_rate=round(correct_sum / total_sum * 100, 1) if total_sum else None,
                mastery=mastery,
            )
        )

    return ClassOverviewResponse(
        class_id=school_class.id,
        class_name=school_class.name,
        categories=[
            ClassOverviewCategory(id=c.id, name=c.name, total_words=totals.get(c.id, 0))
            for c in assigned
        ],
        members=members,
    )


# ── Žiak ─────────────────────────────────────────────────────────────────────

@router.get("/preview/{class_code}", response_model=ClassPreview)
async def class_preview(class_code: str, db: Session = Depends(get_db)):
    """Verejný náhľad pre landing /c/{kód} — bez zoznamu žiakov."""
    school_class = _class_by_code(db, class_code)
    teacher = db.query(User).filter(User.id == school_class.teacher_id).first()
    member_count = (
        db.query(func.count(ClassMember.id))
        .filter(ClassMember.class_id == school_class.id)
        .scalar()
        or 0
    )
    return ClassPreview(
        class_code=school_class.join_code,
        name=school_class.name,
        teacher_name=(teacher.name if teacher else None),
        member_count=member_count,
    )


@router.get("/mine", response_model=list[MyClassResponse])
async def my_memberships(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    rows = (
        db.query(ClassMember, SchoolClass, User)
        .join(SchoolClass, SchoolClass.id == ClassMember.class_id)
        .join(User, User.id == SchoolClass.teacher_id)
        .filter(ClassMember.user_id == current_user.id)
        .order_by(ClassMember.joined_at)
        .all()
    )
    return [
        MyClassResponse(
            class_id=school_class.id,
            class_name=school_class.name,
            teacher_name=teacher.name,
            nickname=member.nickname,
        )
        for member, school_class, teacher in rows
    ]


@router.post("/join")
@limiter.limit("20/hour")
async def join_class(
    data: ClassJoin,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Pridanie prihláseného usera (e-mailového aj pseudonymného) do triedy."""
    school_class = _class_by_code(db, data.class_code)
    if school_class.teacher_id == current_user.id:
        raise HTTPException(status_code=400, detail="Do vlastnej triedy sa nedá pridať.")

    existing = (
        db.query(ClassMember)
        .filter(
            ClassMember.class_id == school_class.id,
            ClassMember.user_id == current_user.id,
        )
        .first()
    )
    if existing:
        return JSONResponse(
            {"message": "Už ste členom tejto triedy.", "class_id": school_class.id, "already_member": True}
        )

    nickname = _clean_nickname(data.nickname or current_user.name or "")
    collision = (
        db.query(ClassMember)
        .filter(ClassMember.class_id == school_class.id, ClassMember.nickname == nickname)
        .first()
    )
    if collision:
        raise HTTPException(
            status_code=409,
            detail="Túto prezývku už niekto v triede používa. Zvoľte inú.",
        )

    db.add(ClassMember(class_id=school_class.id, user_id=current_user.id, nickname=nickname))
    db.commit()
    return JSONResponse(
        {"message": f"Pridané do triedy '{school_class.name}'.", "class_id": school_class.id, "already_member": False}
    )


@router.post("/join-new")
@limiter.limit("60/hour")  # celá trieda sa hlási spoza jednej školskej IP (NAT)
async def join_class_new_student(
    data: ClassJoinNew,
    request: Request,
    db: Session = Depends(get_db),
):
    """Pseudonymná registrácia žiaka — bez e-mailu (GDPR čl. 8, vzor Kahoot)."""
    if request.session.get("user"):
        raise HTTPException(
            status_code=400,
            detail="Ste prihlásený — pridajte sa do triedy existujúcim účtom.",
        )
    school_class = _class_by_code(db, data.class_code)
    nickname = _clean_nickname(data.nickname)

    collision = (
        db.query(ClassMember)
        .filter(ClassMember.class_id == school_class.id, ClassMember.nickname == nickname)
        .first()
    )
    if collision:
        raise HTTPException(
            status_code=409,
            detail="Túto prezývku už niekto v triede používa. Zvoľte inú.",
        )
    error = password_strength_error(data.password)
    if error:
        raise HTTPException(status_code=400, detail=error)

    user = User(
        email=None,
        name=nickname,
        password=hash_password(data.password),
        is_plus=False,
        is_pseudonymous=True,
    )
    db.add(user)
    db.flush()  # kvôli user.id pre membership
    db.add(ClassMember(class_id=school_class.id, user_id=user.id, nickname=nickname))
    user.last_login = utcnow()
    db.commit()

    _set_session_user(request, user)
    logger.info(f"Pseudonymous student joined class {school_class.id} (user {user.id})")
    return JSONResponse(
        {
            "message": f"Vitaj v triede '{school_class.name}'!",
            "class_id": school_class.id,
            "user": request.session["user"],
        }
    )


@router.post("/login")
@limiter.limit("30/minute")  # školský NAT — nesmie zablokovať celú triedu
async def class_login(
    data: ClassLogin,
    request: Request,
    db: Session = Depends(get_db),
):
    """Login pseudonymného žiaka: kód triedy + prezývka + heslo.

    Jednotná chybová hláška + dummy verify (timing) — žiadna enumerácia prezývok.
    """
    code = _normalize_code(data.class_code)
    nickname = " ".join((data.nickname or "").split())

    row = (
        db.query(ClassMember, User)
        .join(SchoolClass, SchoolClass.id == ClassMember.class_id)
        .join(User, User.id == ClassMember.user_id)
        .filter(SchoolClass.join_code == code, ClassMember.nickname == nickname)
        .first()
    )
    if not row:
        try:
            verify_password(data.password, _TIMING_DUMMY_HASH)
        except ValueError:
            pass
        raise HTTPException(status_code=400, detail=INVALID_CLASS_LOGIN)

    member, user = row
    try:
        valid = verify_password(data.password, user.password)
    except ValueError:
        valid = False
    if not valid:
        raise HTTPException(status_code=400, detail=INVALID_CLASS_LOGIN)

    user.last_login = utcnow()
    db.commit()
    _set_session_user(request, user)
    return JSONResponse({"message": "Prihlásenie úspešné.", "user": request.session["user"]})


@router.post("/{class_id}/leave")
async def leave_class(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    deleted = (
        db.query(ClassMember)
        .filter(ClassMember.class_id == class_id, ClassMember.user_id == current_user.id)
        .delete(synchronize_session=False)
    )
    db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Nie ste členom tejto triedy.")
    # word_progress zámerne ostáva — pri návrate do triedy pokrok pokračuje.
    return JSONResponse({"message": "Odišli ste z triedy."})
