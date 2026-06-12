from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.word import KnowledgeLevel, Word


def empty_level_counts() -> dict:
    return {level.value: 0 for level in KnowledgeLevel}


def empty_level_counts_float() -> dict:
    return {level.value: 0.0 for level in KnowledgeLevel}


def get_category_word_summary(db: Session, user_id: int, category_ids: list[int]) -> dict:
    if not category_ids:
        return {}

    rows = (
        db.query(
            Word.category_id,
            Word.knowledge_level,
            func.count(Word.id),
        )
        .filter(
            Word.user_id == user_id,
            Word.category_id.in_(category_ids),
        )
        .group_by(Word.category_id, Word.knowledge_level)
        .all()
    )

    summary = {category_id: empty_level_counts() for category_id in category_ids}
    for category_id, level, count in rows:
        level_value = level.value if hasattr(level, "value") else level
        if category_id in summary:
            summary[category_id][level_value] = count

    result = {}
    for category_id in category_ids:
        level_counts = summary[category_id]
        total_words = sum(level_counts.values())
        if total_words > 0:
            level_percentages = {
                key: round(value / total_words * 100, 1)
                for key, value in level_counts.items()
            }
        else:
            level_percentages = empty_level_counts_float()

        result[category_id] = {
            "total_words": total_words,
            "level_counts": level_counts,
            "level_percentages": level_percentages,
        }

    return result


def get_user_level_counts(db: Session, user_id: int) -> dict:
    rows = (
        db.query(
            Word.knowledge_level,
            func.count(Word.id),
        )
        .filter(Word.user_id == user_id)
        .group_by(Word.knowledge_level)
        .all()
    )

    level_counts = empty_level_counts()
    for level, count in rows:
        level_value = level.value if hasattr(level, "value") else level
        level_counts[level_value] = count
    return level_counts
