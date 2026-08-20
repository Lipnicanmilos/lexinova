from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import and_, case, func
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.word import KnowledgeLevel, Word
from app.models.test_session import TestSession
from app.models.word_level_event import WordLevelEvent
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


def get_category_word_summary_overlay(db: Session, user_id: int, category_ids: list[int]) -> dict:
    """Summary triednych (cudzích) sád z pohľadu žiaka.

    Pokrok žiaka na cudzích slovách žije vo word_progress — slovo bez záznamu
    je „dont_know". Rovnaký tvar výstupu ako get_category_word_summary.
    """
    from app.models.word_progress import WordProgress  # lokálne kvôli poradiu importov

    if not category_ids:
        return {}

    totals = dict(
        db.query(Word.category_id, func.count(Word.id))
        .filter(Word.category_id.in_(category_ids))
        .group_by(Word.category_id)
        .all()
    )
    rows = (
        db.query(
            Word.category_id,
            WordProgress.knowledge_level,
            func.count(WordProgress.id),
        )
        .join(WordProgress, WordProgress.word_id == Word.id)
        .filter(
            WordProgress.user_id == user_id,
            Word.category_id.in_(category_ids),
        )
        .group_by(Word.category_id, WordProgress.knowledge_level)
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
        total_words = totals.get(category_id, 0)
        counted = sum(level_counts.values())
        # slová bez progress záznamu = ešte netestované → dont_know
        level_counts["dont_know"] += max(total_words - counted, 0)
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


def get_word_aggregates(db: Session, user_id: int, stale_after_days: int = 7) -> dict:
    """Všetky čísla o slovíčkach jedným dotazom.

    Predtým to bolo sedem samostatných dotazov (count, dva sumy, netestované,
    dávno netestované, priemer opakovaní, počty podľa úrovne). Nad vzdialenou
    databázou nestojí čas na výpočte, ale na siedmich round-tripoch — jeden
    prechod tabuľkou s podmienenými agregátmi vráti to isté.
    """
    stale_before = utcnow() - timedelta(days=stale_after_days)

    def count_if(condition):
        return func.count(case((condition, Word.id)))

    level_columns = {
        level: count_if(Word.knowledge_level == level) for level in KnowledgeLevel
    }

    row = (
        db.query(
            func.count(Word.id),
            func.coalesce(func.sum(Word.times_tested), 0),
            func.coalesce(func.sum(Word.times_correct), 0),
            count_if(Word.times_tested == 0),
            count_if(and_(Word.times_tested > 0, Word.last_tested < stale_before)),
            func.avg(
                case((
                    and_(
                        Word.knowledge_level == KnowledgeLevel.KNOW,
                        Word.times_tested > 0,
                    ),
                    Word.times_tested,
                ))
            ),
            *level_columns.values(),
        )
        .filter(Word.user_id == user_id)
        .one()
    )

    total, tested, correct, untested, to_review, avg_to_master = row[:6]
    level_counts = empty_level_counts()
    for level, count in zip(level_columns, row[6:]):
        level_counts[level.value] = int(count or 0)

    return {
        "total_words": int(total or 0),
        "tests_taken": int(tested or 0),
        "times_correct": int(correct or 0),
        "untested": int(untested or 0),
        "to_review": int(to_review or 0),
        "avg_reviews_to_master": round(float(avg_to_master), 1) if avg_to_master else None,
        "level_counts": level_counts,
    }


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


# Ako ďaleko dozadu sa pozeráme pri sérii dní. Denné riadky sú lacné (jeden na
# deň), ale načítať celú históriu netreba — 400 dní pokryje aj ročnú sériu.
HISTORY_WINDOW_DAYS = 400


def get_history_stats(db: Session, user_id: int, today: date = None, days: int = 14) -> dict:
    """Streak, denná aktivita (posledných `days` dní) a počty testov za 7/30 dní.

    Agreguje sa v databáze po dňoch: predtým sa načítali **všetky** riadky
    `test_sessions` používateľa a spočítali v Pythone, takže objem rástol s
    používaním appky, hoci graf potrebuje 30 dní.

    Odolné voči chýbajúcej tabuľke (starší deploy bez migrácie) — vráti nuly.
    """
    today = today or utcnow().date()
    empty = {
        "streak_days": 0,
        "tests_total": 0,
        "tests_7d": 0,
        "tests_30d": 0,
        "reviews_7d": 0,
        "accuracy_7d": None,
        "accuracy_prev_7d": None,
        "activity": [
            {"date": (today - timedelta(days=i)).isoformat(), "tests": 0, "reviews": 0, "accuracy": None}
            for i in range(days - 1, -1, -1)
        ],
    }

    day = func.date(TestSession.created_at)
    since = today - timedelta(days=HISTORY_WINDOW_DAYS)
    try:
        rows = (
            db.query(
                day.label("day"),
                TestSession.kind,
                func.count(TestSession.id),
                func.coalesce(func.sum(TestSession.total), 0),
                func.coalesce(func.sum(TestSession.correct), 0),
            )
            .filter(TestSession.user_id == user_id, TestSession.created_at >= since)
            .group_by(day, TestSession.kind)
            .all()
        )
        # Celkový počet testov je „za celý čas", takže mimo okna — vlastný COUNT.
        # Opakovanie (auto-play) sa doň nepočíta, nie je to test.
        tests_total = int(
            db.query(func.count(TestSession.id))
            .filter(TestSession.user_id == user_id, TestSession.kind != "review")
            .scalar()
            or 0
        )
    except (ProgrammingError, OperationalError):
        db.rollback()
        return empty

    # Opakovanie (auto-play) sa ráta do série dní aj do grafu, ale nikdy do
    # úspešnosti — pri prehrávaní sa neodpovedá, takže correct je vždy 0 a
    # priemer by strhlo na nulu.
    active_days = set()
    # date -> [poctov testov, kariet v testoch, spravnych, poctov opakovani]
    daily = defaultdict(lambda: [0, 0, 0, 0])

    for day_value, kind, count, total, correct in rows:
        if day_value is None:
            continue
        d = day_value if isinstance(day_value, date) else date.fromisoformat(str(day_value)[:10])
        active_days.add(d)
        agg = daily[d]
        if kind == "review":
            agg[3] += int(count or 0)
            continue
        agg[0] += int(count or 0)
        agg[1] += int(total or 0)
        agg[2] += int(correct or 0)

    activity = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        tests, total, correct, reviews = daily.get(d, (0, 0, 0, 0))
        activity.append({
            "date": d.isoformat(),
            "tests": tests,
            "reviews": reviews,
            "accuracy": round(correct / total * 100) if total else None,
        })

    tests_7d = sum(daily[d][0] for d in daily if d > today - timedelta(days=7))
    tests_30d = sum(daily[d][0] for d in daily if d > today - timedelta(days=30))
    reviews_7d = sum(daily[d][3] for d in daily if d > today - timedelta(days=7))

    def window_accuracy(frm: date, to: date):
        """Úspešnosť (%) z kariet v dňoch <frm, to>; None ak žiadny test."""
        total = sum(daily[d][1] for d in daily if frm <= d <= to)
        correct = sum(daily[d][2] for d in daily if frm <= d <= to)
        return round(correct / total * 100) if total else None

    return {
        "streak_days": compute_streak(active_days, today),
        # Skutočný počet absolvovaných testov (riadky v test_sessions). Nezamieňať
        # so SUM(times_tested) v users.py — to je počet zodpovedaných kariet.
        "tests_total": tests_total,
        "tests_7d": tests_7d,
        "tests_30d": tests_30d,
        "reviews_7d": reviews_7d,
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


# ── História úrovní ──────────────────────────────────────────────────────────
# Zápis aj čítanie sú "best effort": ak migrácia word_level_events ešte
# nebežala, appka funguje ďalej a metrika sa ukáže ako 0.


def record_level_changes(db: Session, events: list[dict]) -> None:
    """Uloží zmeny úrovne slov. Volať až PO commite samotných slov — tu si
    vlastný rollback nesmie vziať so sebou uložený pokrok."""
    if not events:
        return
    try:
        db.add_all([
            WordLevelEvent(
                user_id=e["user_id"],
                word_id=e["word_id"],
                previous_level=e.get("previous_level"),
                level=e["level"],
            )
            for e in events
        ])
        db.commit()
    except (ProgrammingError, OperationalError):
        db.rollback()


def level_value(level) -> str | None:
    """Enum aj string vrátia rovnaký string (v DB je stĺpec VARCHAR)."""
    if level is None:
        return None
    return level.value if hasattr(level, "value") else str(level)


def get_learned_counts(db: Session, user_id: int, days: tuple = (7, 30)) -> dict:
    """Koľko slov sa za dané okná dostalo na úroveň "Viem".

    Každé slovo sa počíta raz aj keď ho používateľ medzitým zabudol a znova
    naučil — inak by jedno kolísajúce slovo nafúklo číslo.
    """
    result = {f"learned_{d}d": 0 for d in days}
    now = utcnow()
    # Okná (7 a 30 dní) idú jedným dotazom — podmienený COUNT DISTINCT na okno.
    columns = [
        func.count(
            func.distinct(
                case((WordLevelEvent.created_at >= now - timedelta(days=d), WordLevelEvent.word_id))
            )
        )
        for d in days
    ]
    try:
        row = (
            db.query(*columns)
            .filter(
                WordLevelEvent.user_id == user_id,
                WordLevelEvent.level == KnowledgeLevel.KNOW.value,
            )
            .one()
        )
    except (ProgrammingError, OperationalError):
        db.rollback()
        return result
    for d, count in zip(days, row):
        result[f"learned_{d}d"] = int(count or 0)
    return result


# ── Najslabšie kategórie ────────────────────────────────────────────────────

WEAK_CATEGORY_MIN_TESTED = 5


def get_weak_categories(db: Session, user_id: int, limit: int = 3) -> list:
    """Kategórie s najnižšou úspešnosťou — kde sa oplatí zabrať.

    Berieme len kategórie s aspoň WEAK_CATEGORY_MIN_TESTED zodpovedanými
    kartami, inak by rebríčku kraľovalo slovo skúšané raz a raz zle.
    """
    rows = (
        db.query(
            Category.id,
            Category.name,
            func.sum(Word.times_tested),
            func.sum(Word.times_correct),
            func.count(Word.id),
        )
        .join(Word, Word.category_id == Category.id)
        .filter(Category.user_id == user_id, Word.times_tested > 0)
        .group_by(Category.id, Category.name)
        .all()
    )

    categories = []
    for category_id, name, tested, correct, words in rows:
        tested = int(tested or 0)
        if tested < WEAK_CATEGORY_MIN_TESTED:
            continue
        categories.append({
            "id": category_id,
            "name": name,
            "accuracy": round(int(correct or 0) / tested * 100),
            "words": int(words or 0),
            "times_tested": tested,
        })

    categories.sort(key=lambda c: (c["accuracy"], -c["times_tested"]))
    return categories[:limit]
