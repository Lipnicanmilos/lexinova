"""Lazy „anacron" scheduler — expirácia PLUS, atomický claim, dobiehanie behov.

Testy bežia proti tej istej SQLite DB ako aplikácia (fixture `db_factory`),
scheduleru ju odovzdávame cez `session_factory=`.
"""
from datetime import date, timedelta

import pytest

from app.models.job_run import JobRun
from app.models.user import User
from app.services import scheduler
from app.services.jobs import expire_subscriptions
from app.utils import utcnow


@pytest.fixture(autouse=True)
def _clean_job_runs(db_factory):
    """Každý test začína s prázdnou tabuľkou job_runs."""
    db = db_factory()
    try:
        db.query(JobRun).delete()
        db.commit()
    finally:
        db.close()


def _make_user(db, email, **kw):
    user = User(email=email, password="x", **kw)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# --- expire_subscriptions job ---------------------------------------------

def test_expire_subscriptions_turns_off_expired(db_factory):
    db = db_factory()
    try:
        past = utcnow() - timedelta(days=1)
        future = utcnow() + timedelta(days=5)
        expired = _make_user(db, "sched-exp@example.com", is_plus=True,
                             plus_status="active", plus_expires_at=past)
        active = _make_user(db, "sched-act@example.com", is_plus=True,
                            plus_status="active", plus_expires_at=future)
        no_expiry = _make_user(db, "sched-perm@example.com", is_plus=True,
                               plus_status="active", plus_expires_at=None)

        expire_subscriptions(db)

        db.refresh(expired); db.refresh(active); db.refresh(no_expiry)
        assert expired.is_plus is False
        assert expired.plus_status == "expired"
        assert active.is_plus is True          # ešte neexpiroval
        assert no_expiry.is_plus is True        # bez expirácie sa nevypína
    finally:
        db.close()


def test_expire_subscriptions_idempotent(db_factory):
    """Druhý beh nič nemení (job je idempotentný)."""
    db = db_factory()
    try:
        user = _make_user(db, "sched-exp2@example.com", is_plus=True, plus_status="active",
                          plus_expires_at=utcnow() - timedelta(hours=1))
        expire_subscriptions(db)
        remaining_after_first = db.query(User).filter(User.is_plus.is_(True)).count()
        expire_subscriptions(db)  # nesmie spadnúť ani nič dodatočne meniť
        remaining_after_second = db.query(User).filter(User.is_plus.is_(True)).count()
        assert remaining_after_second == remaining_after_first
        db.refresh(user)
        assert user.is_plus is False
    finally:
        db.close()


# --- atomický claim --------------------------------------------------------

def test_claim_is_once_per_day(db_factory):
    db = db_factory()
    try:
        today = date.today()
        scheduler._ensure_row(db, "demo")
        assert scheduler._claim(db, "demo", today) is True   # prvý nárok vyhrá
        assert scheduler._claim(db, "demo", today) is False  # dnes už bežal
        # ďalší deň sa dá nárokovať znova
        assert scheduler._claim(db, "demo", today + timedelta(days=1)) is True
    finally:
        db.close()


# --- run_due_jobs: dobiehanie, idempotencia, hodinová brána ----------------

@pytest.fixture
def temp_job():
    """Zaregistruje dočasný počítací job a po teste ho odregistruje."""
    calls = {"n": 0}

    def _job(db):
        calls["n"] += 1

    def _register(run_after_hour=0):
        scheduler.register_job("test_counter", _job, run_after_hour=run_after_hour)
        return calls

    yield _register
    scheduler._REGISTRY[:] = [j for j in scheduler._REGISTRY if j.name != "test_counter"]


def test_run_due_jobs_runs_once_per_day(db_factory, temp_job):
    calls = temp_job(run_after_hour=0)
    scheduler.run_due_jobs(session_factory=db_factory)
    scheduler.run_due_jobs(session_factory=db_factory)  # druhý beh v ten deň nič
    assert calls["n"] == 1

    row = db_factory().query(JobRun).filter(JobRun.job_name == "test_counter").first()
    assert row.last_status == "ok"
    assert row.last_run_date == date.today()


def test_run_due_jobs_respects_hour_gate(db_factory, temp_job, monkeypatch):
    """Pred cieľovou hodinou sa job nespustí; po nej áno."""
    calls = temp_job(run_after_hour=23)

    fixed = utcnow().replace(hour=10)
    monkeypatch.setattr(scheduler, "utcnow", lambda: fixed)
    scheduler.run_due_jobs(session_factory=db_factory)
    assert calls["n"] == 0  # 10:00 < 23:00 → brána zavretá

    monkeypatch.setattr(scheduler, "utcnow", lambda: fixed.replace(hour=23))
    scheduler.run_due_jobs(session_factory=db_factory)
    assert calls["n"] == 1  # 23:00 → spustené


def test_failing_job_does_not_raise_and_marks_error(db_factory):
    """Chyba jobu sa zachytí, zapíše ako error a nezhodí beh."""
    def _boom(db):
        raise RuntimeError("boom")

    scheduler.register_job("test_boom", _boom, run_after_hour=0)
    try:
        scheduler.run_due_jobs(session_factory=db_factory)  # nesmie vyhodiť
        row = db_factory().query(JobRun).filter(JobRun.job_name == "test_boom").first()
        assert row.last_status == "error"
        assert "boom" in (row.last_error or "")
    finally:
        scheduler._REGISTRY[:] = [j for j in scheduler._REGISTRY if j.name != "test_boom"]
