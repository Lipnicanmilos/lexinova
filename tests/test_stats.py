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
