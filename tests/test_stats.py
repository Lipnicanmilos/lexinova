"""Štatistiky — streak, odznaky a história (čisté funkcie + endpoint polia)."""
from datetime import date, timedelta

from app.services.stats_service import compute_streak, build_badges


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
