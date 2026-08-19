"""Štatistiky — streak, odznaky a história (čisté funkcie + endpoint polia)."""
from datetime import date, datetime, timedelta

# Alias — pytest by inak triedu TestSession zbieral ako testovaciu (prefix "Test")
from app.models.test_session import TestSession as SessionModel
from app.services.stats_service import compute_streak, build_badges, get_history_stats


TODAY = date(2026, 6, 30)


def test_streak_empty():
    assert compute_streak(set(), TODAY) == 0


def test_streak_counts_consecutive_including_today():
    days = {TODAY, TODAY - timedelta(days=1), TODAY - timedelta(days=2)}
    assert compute_streak(days, TODAY) == 3


def test_streak_today_only():
    assert compute_streak({TODAY}, TODAY) == 1


def test_streak_from_yesterday_when_not_active_today():
    # Aktivita včera a predvčerom, dnes ešte nie → séria sa neláme, je 2.
    days = {TODAY - timedelta(days=1), TODAY - timedelta(days=2)}
    assert compute_streak(days, TODAY) == 2


def test_streak_breaks_with_gap():
    # Aktivita dnes a pred 3 dňami (medzera) → len dnešný deň.
    days = {TODAY, TODAY - timedelta(days=3)}
    assert compute_streak(days, TODAY) == 1


def test_streak_zero_when_stale():
    # Posledná aktivita pred 2 dňami (ani dnes, ani včera) → 0.
    days = {TODAY - timedelta(days=2)}
    assert compute_streak(days, TODAY) == 0


def test_badges_earned_thresholds():
    badges = {b["id"]: b for b in build_badges(
        {"categories": 1, "mastered": 50, "streak": 7, "reviews": 120}
    )}
    assert badges["mastered10"]["earned"] is True
    assert badges["mastered50"]["earned"] is True
    assert badges["mastered100"]["earned"] is False
    assert badges["streak3"]["earned"] is True
    assert badges["streak7"]["earned"] is True
    assert badges["reviews100"]["earned"] is True
    assert badges["reviews500"]["earned"] is False
    assert badges["explorer"]["earned"] is False  # len 1 kategória
    # current/target sa prenášajú pre progress bar
    assert badges["mastered100"]["current"] == 50
    assert badges["mastered100"]["target"] == 100


def test_badges_empty_metrics():
    badges = build_badges({})
    assert all(b["earned"] is False for b in badges)
    assert len(badges) == 9


def test_stats_endpoint_requires_auth(client):
    r = client.get("/api/user/stats")
    assert r.status_code in (401, 403)


def test_history_accuracy_windows(db_factory):
    """accuracy_7d = posledných 7 dní vrátane dnes; prev = 7 dní pred nimi."""
    db = db_factory()
    try:
        user_id = 987654  # izolované ID — žiadny iný test nezapisuje TestSession
        # Tento týždeň: 8/10 správne → 80 %
        db.add(SessionModel(
            user_id=user_id, total=10, correct=8,
            created_at=datetime(2026, 6, 28, 12, 0),
        ))
        # Minulý týždeň: 5/10 správne → 50 %
        db.add(SessionModel(
            user_id=user_id, total=10, correct=5,
            created_at=datetime(2026, 6, 20, 12, 0),
        ))
        db.commit()

        h = get_history_stats(db, user_id, today=TODAY, days=30)
        assert h["accuracy_7d"] == 80
        assert h["accuracy_prev_7d"] == 50
        assert len(h["activity"]) == 30
    finally:
        db.query(SessionModel).filter(SessionModel.user_id == 987654).delete()
        db.commit()
        db.close()


def test_history_accuracy_none_without_tests(db_factory):
    db = db_factory()
    try:
        h = get_history_stats(db, 999999, today=TODAY)
        assert h["accuracy_7d"] is None
        assert h["accuracy_prev_7d"] is None
    finally:
        db.close()


# ── História úrovní a najslabšie kategórie ──

def test_learned_counts_dedupes_and_respects_window(db_factory):
    """Slovo naučené-zabudnuté-naučené sa počíta raz; staršie okno nezasahuje."""
    from app.models.word_level_event import WordLevelEvent
    from app.services.stats_service import get_learned_counts
    from app.utils import utcnow

    db = db_factory()
    user_id = 987655
    now = utcnow()
    try:
        for word_id, level, days_ago in [
            (1, "know", 1),        # naučené dnes
            (1, "dont_know", 3),   # to isté slovo medzitým zabudnuté a znova naučené
            (1, "know", 4),
            (2, "know", 6),        # druhé slovo v okne 7 dní
            (3, "know", 20),       # mimo 7 dní, ale v 30
            (4, "learning", 1),    # nie "know" → nepočíta sa
        ]:
            db.add(WordLevelEvent(
                user_id=user_id, word_id=word_id, level=level,
                created_at=now - timedelta(days=days_ago),
            ))
        db.commit()

        counts = get_learned_counts(db, user_id)
        assert counts["learned_7d"] == 2    # slová 1 a 2, slovo 1 len raz
        assert counts["learned_30d"] == 3   # + slovo 3
    finally:
        db.query(WordLevelEvent).filter(WordLevelEvent.user_id == user_id).delete()
        db.commit()
        db.close()


def test_weak_categories_ranks_worst_first_and_skips_thin_data(db_factory):
    from app.models.category import Category
    from app.models.word import Word
    from app.services.stats_service import get_weak_categories

    db = db_factory()
    user_id = 987656
    try:
        def make_category(name, words):
            category = Category(name=name, user_id=user_id)
            db.add(category)
            db.flush()
            for tested, correct in words:
                db.add(Word(
                    original_word="w", translation="s", category_id=category.id,
                    user_id=user_id, times_tested=tested, times_correct=correct,
                ))
            return category

        weak = make_category("Slabá", [(10, 3)])       # 30 %
        strong = make_category("Silná", [(10, 9)])     # 90 %
        make_category("Málo dát", [(2, 0)])            # 0 %, ale len 2 karty
        db.commit()

        result = get_weak_categories(db, user_id)
        assert [c["id"] for c in result] == [weak.id, strong.id]
        assert result[0]["accuracy"] == 30
        assert result[1]["accuracy"] == 90
    finally:
        db.query(Word).filter(Word.user_id == user_id).delete()
        db.query(Category).filter(Category.user_id == user_id).delete()
        db.commit()
        db.close()


# ── Agregáty nad slovíčkami (jeden dotaz namiesto siedmich) ──

def test_word_aggregates_matches_per_word_reality(db_factory):
    """Jeden agregačný dotaz musí dať to isté, čo počítanie po riadkoch."""
    from app.models.word import KnowledgeLevel, Word
    from app.services.stats_service import get_word_aggregates
    from app.utils import utcnow

    db = db_factory()
    user_id = 987657
    now = utcnow()
    try:
        rows = [
            # (level, times_tested, times_correct, last_tested)
            (KnowledgeLevel.KNOW,       4, 4, now - timedelta(days=1)),
            (KnowledgeLevel.KNOW,       2, 1, now - timedelta(days=30)),   # dávno netestované
            (KnowledgeLevel.DONT_KNOW,  3, 0, now - timedelta(days=20)),   # dávno netestované
            (KnowledgeLevel.DONT_KNOW,  0, 0, None),                       # netestované
            (KnowledgeLevel.LEARNING,   0, 0, None),                       # netestované
        ]
        for i, (level, tested, correct, last) in enumerate(rows):
            db.add(Word(
                original_word=f"w{i}", translation=f"p{i}", category_id=1,
                user_id=user_id, knowledge_level=level,
                times_tested=tested, times_correct=correct, last_tested=last,
            ))
        db.commit()

        agg = get_word_aggregates(db, user_id)
        assert agg["total_words"] == 5
        assert agg["tests_taken"] == 9        # 4+2+3
        assert agg["times_correct"] == 5      # 4+1
        assert agg["untested"] == 2           # times_tested == 0
        assert agg["to_review"] == 2          # testované, ale starším než 7 dní
        assert agg["level_counts"] == {"know": 2, "learning": 1, "dont_know": 2}
        assert agg["avg_reviews_to_master"] == 3.0   # (4+2)/2, len úroveň "Viem"
    finally:
        db.query(Word).filter(Word.user_id == user_id).delete()
        db.commit()
        db.close()


def test_word_aggregates_empty_user_returns_zeros(db_factory):
    """Nový účet bez slovíčok — žiadne delenie nulou, avg je None, nie 0."""
    from app.services.stats_service import get_word_aggregates

    db = db_factory()
    try:
        agg = get_word_aggregates(db, 999998)
        assert agg["total_words"] == 0
        assert agg["tests_taken"] == 0
        assert agg["untested"] == 0
        assert agg["to_review"] == 0
        assert agg["avg_reviews_to_master"] is None
        assert agg["level_counts"] == {"know": 0, "learning": 0, "dont_know": 0}
    finally:
        db.close()
