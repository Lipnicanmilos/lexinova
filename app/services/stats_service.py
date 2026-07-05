from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.models.word import KnowledgeLevel, Word
from app.models.test_session import TestSession
from app.utils import utcnow


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


# ── História / streak / aktivita / gamifikácia ───────────────────────────────

def compute_streak(active_days: set, today: date) -> int:
    """Počet po sebe idúcich dní s aktivitou končiacich dnes (alebo včera).

    Ak je aktivita dnes, ráta sa od dnes; ak nie ale bola včera, od včera
    (séria sa „neláme" hneď po polnoci). Inak 0.
    """
    if not active_days:
        return 0
    if today in active_days:
        cursor = today
    elif (today - timedelta(days=1)) in active_days:
        cursor = today - timedelta(days=1)
    else:
        return 0
    streak = 0
    while cursor in active_days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def get_history_stats(db: Session, user_id: int, today: date = None, days: int = 14) -> dict:
    """Streak, denná aktivita (posledných `days` dní) a počty testov za 7/30 dní.

    Odolné voči chýbajúcej tabuľke (starší deploy bez migrácie) — vráti nuly.
    """
    today = today or utcnow().date()
    empty = {
        "streak_days": 0,
        "tests_7d": 0,
        "tests_30d": 0,
        "accuracy_7d": None,
        "accuracy_prev_7d": None,
        "activity": [
            {"date": (today - timedelta(days=i)).isoformat(), "tests": 0, "accuracy": None}
            for i in range(days - 1, -1, -1)
        ],
    }
    try:
        rows = (
            db.query(TestSession.created_at, TestSession.total, TestSession.correct)
            .filter(TestSession.user_id == user_id)
            .all()
        )
    except (ProgrammingError, OperationalError):
        db.rollback()
        return empty

    active_days = set()
    daily = defaultdict(lambda: [0, 0, 0])  # date -> [pocet_testov, total_kariet, spravne]
    for created_at, total, correct in rows:
        if created_at is None:
            continue
        d = created_at.date()
        active_days.add(d)
        agg = daily[d]
        agg[0] += 1
        agg[1] += total or 0
        agg[2] += correct or 0

    activity = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        tests, total, correct = daily.get(d, (0, 0, 0))
        activity.append({
            "date": d.isoformat(),
            "tests": tests,
            "accuracy": round(correct / total * 100) if total else None,
        })

    tests_7d = sum(daily[d][0] for d in daily if d > today - timedelta(days=7))
    tests_30d = sum(daily[d][0] for d in daily if d > today - timedelta(days=30))

    def window_accuracy(frm: date, to: date):
        """Úspešnosť (%) z kariet v dňoch <frm, to>; None ak žiadny test."""
        total = sum(daily[d][1] for d in daily if frm <= d <= to)
        correct = sum(daily[d][2] for d in daily if frm <= d <= to)
        return round(correct / total * 100) if total else None

    return {
        "streak_days": compute_streak(active_days, today),
        "tests_7d": tests_7d,
        "tests_30d": tests_30d,
        "accuracy_7d": window_accuracy(today - timedelta(days=6), today),
        "accuracy_prev_7d": window_accuracy(today - timedelta(days=13), today - timedelta(days=7)),
        "activity": activity,
    }


# Definície odznakov: (id, ikona, EN, SK, metrika, cieľ). Odvodené z existujúcich
# dát — žiadna extra DB, prepočítavajú sa pri každom načítaní štatistík.
BADGE_DEFS = [
    ("starter",     "🌱", "First category",    "Prvá kategória",   "categories", 1),
    ("explorer",    "🧭", "5 categories",      "5 kategórií",      "categories", 5),
    ("mastered10",  "⭐", "10 words mastered", "10 zvládnutých",   "mastered",   10),
    ("mastered50",  "🌟", "50 words mastered", "50 zvládnutých",   "mastered",   50),
    ("mastered100", "🏆", "100 words mastered","100 zvládnutých",  "mastered",   100),
    ("streak3",     "🔥", "3-day streak",      "3 dni v rade",     "streak",     3),
    ("streak7",     "🔥", "7-day streak",      "7 dní v rade",     "streak",     7),
    ("reviews100",  "💪", "100 reviews",       "100 opakovaní",    "reviews",    100),
    ("reviews500",  "🚀", "500 reviews",       "500 opakovaní",    "reviews",    500),
]


def build_badges(metrics: dict) -> list:
    """Z metrík (categories, mastered, streak, reviews) zostaví zoznam odznakov
    s príznakom `earned` a postupom k cieľu."""
    badges = []
    for badge_id, icon, en, sk, metric, target in BADGE_DEFS:
        current = int(metrics.get(metric, 0) or 0)
        badges.append({
            "id": badge_id,
            "icon": icon,
            "label_en": en,
            "label_sk": sk,
            "earned": current >= target,
            "current": current,
            "target": target,
        })
    return badges
