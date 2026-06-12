from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.category import Category
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.services.stats_service import (
    empty_level_counts,
    empty_level_counts_float,
    get_category_word_summary,
)

router = APIRouter(prefix="/api/v1/categories", tags=["categories"])


def _get_current_user(request: Request, db: Session) -> User:
    user_session = request.session.get("user")
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.query(User).filter(User.id == user_session["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("", response_model=list[CategoryResponse])
async def get_categories(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    categories = db.query(Category).filter(Category.user_id == user.id).all()
    summaries = get_category_word_summary(db, user.id, [category.id for category in categories])

    result = []
    for category in categories:
        summary = summaries.get(
            category.id,
            {
                "total_words": 0,
                "level_counts": empty_level_counts(),
                "level_percentages": empty_level_counts_float(),
            },
        )
        result.append(
            CategoryResponse(
                id=category.id,
                name=category.name,
                description=category.description,
                user_id=category.user_id,
                created_at=category.created_at,
                total_words=summary["total_words"],
                level_counts=summary["level_counts"],
                level_percentages=summary["level_percentages"],
            )
        )
    return result


@router.post("", response_model=CategoryResponse)
async def create_category(
    category_data: CategoryCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_current_user(request, db)

    category_count = db.query(Category).filter(Category.user_id == user.id).count()
    if category_count >= 5:
        raise HTTPException(status_code=400, detail="Maximum limit of 5 categories reached")

    existing_category = (
        db.query(Category)
        .filter(Category.name == category_data.name, Category.user_id == user.id)
        .first()
    )
    if existing_category:
        raise HTTPException(status_code=400, detail="Category with this name already exists")

    new_category = Category(
        name=category_data.name,
        description=category_data.description,
        user_id=user.id,
    )
    db.add(new_category)
    db.commit()
    db.refresh(new_category)
    return new_category


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    category_update: CategoryUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_current_user(request, db)
    category = (
        db.query(Category)
        .filter(Category.id == category_id, Category.user_id == user.id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    for field, value in category_update.dict(exclude_unset=True).items():
        setattr(category, field, value)

    db.commit()
    db.refresh(category)

    summary = get_category_word_summary(db, user.id, [category.id])[category.id]
    return CategoryResponse(
        id=category.id,
        name=category.name,
        description=category.description,
        created_at=category.created_at,
        user_id=category.user_id,
        total_words=summary["total_words"],
        level_counts=summary["level_counts"],
        level_percentages=summary["level_percentages"],
    )


@router.delete("/{category_id}")
async def delete_category(category_id: int, request: Request, db: Session = Depends(get_db)):
    user_session = request.session.get("user")
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    category = (
        db.query(Category)
        .filter(Category.id == category_id, Category.user_id == user_session["id"])
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    db.delete(category)
    db.commit()
    return {"message": "Category deleted successfully"}


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category_detail(category_id: int, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    category = (
        db.query(Category)
        .filter(Category.id == category_id, Category.user_id == user.id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    summary = get_category_word_summary(db, user.id, [category.id])[category.id]
    return CategoryResponse(
        id=category.id,
        name=category.name,
        description=category.description,
        user_id=category.user_id,
        created_at=category.created_at,
        total_words=summary["total_words"],
        level_counts=summary["level_counts"],
        level_percentages=summary["level_percentages"],
    )


@router.get("/{category_id}/stats")
async def get_category_stats(category_id: int, request: Request, db: Session = Depends(get_db)):
    user_session = request.session.get("user")
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    category = (
        db.query(Category)
        .filter(Category.id == category_id, Category.user_id == user_session["id"])
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    summary = get_category_word_summary(db, user_session["id"], [category_id])[category_id]
    total_words = summary["total_words"]
    level_counts = summary["level_counts"]

    stats = {
        "total_words": total_words,
        "dont_know_percentage": round((level_counts.get("dont_know", 0) / total_words * 100), 1)
        if total_words > 0
        else 0,
        "learning_percentage": round((level_counts.get("learning", 0) / total_words * 100), 1)
        if total_words > 0
        else 0,
        "know_percentage": round((level_counts.get("know", 0) / total_words * 100), 1)
        if total_words > 0
        else 0,
    }
    return JSONResponse(stats)

