"""História aktivity sa agreguje v databáze, nie načítaním všetkých riadkov.

Pôvodne `get_history_stats` stiahlo **všetky** `test_sessions` používateľa a
spočítalo ich v Pythone. Graf pritom potrebuje 30 dní. Objem tak rástol s
používaním appky — pri vzdialenej databáze je to presne ten typ dotazu, ktorý
sa časom zmení na problém.
"""
from datetime import date, datetime, timedelta

from sqlalchemy import event

# Alias — pytest by inak triedu TestSession zbieral ako testovaciu (prefix „Test")
from app.models.test_session import TestSession as SessionModel
from app.services.stats_service import HISTORY_WINDOW_DAYS, get_history_stats

TODAY = date(2026, 6, 30)
USER_ID = 987660


def _seed(db, days_ago_list, kind=None):
    for days_ago in days_ago_list:
        db.add(SessionModel(
            user_id=USER_ID, total=10, correct=8, kind=kind,
            created_at=datetime.combine(TODAY - timedelta(days=days_ago), datetime.min.time()),
        ))
    db.commit()


def test_history_reads_a_bounded_number_of_rows(db_factory):
    """Dva dotazy bez ohľadu na to, koľko testov používateľ absolvoval."""
    db = db_factory()
    try:
        _seed(db, range(0, 120))          # 120 dní testov

        statements = []
        engine = db.get_bind()

        @event.listens_for(engine, "before_cursor_execute")
        def _collect(conn, cursor, statement, params, context, executemany):
            statements.append(statement)

        try:
            history = get_history_stats(db, USER_ID, today=TODAY, days=30)
        finally:
            event.remove(engine, "before_cursor_execute", _collect)

        assert len(statements) == 2, f"agregácia + počet, nie {len(statements)} dotazov"
        # Ani jeden dotaz nesmie ťahať riadky bez agregácie.
        assert all('count(' in st.lower() for st in statements), statements
        assert len(history["activity"]) == 30
        assert history["tests_total"] == 120
    finally:
        db.query(SessionModel).filter(SessionModel.user_id == USER_ID).delete()
        db.commit()
        db.close()


def test_streak_survives_aggregation(db_factory):
    """Séria dní sa počíta z dní s aktivitou — agregácia ju nesmie rozbiť."""
    db = db_factory()
    try:
        _seed(db, [0, 1, 2, 4])           # dnes, včera, predvčerom, potom medzera

        history = get_history_stats(db, USER_ID, today=TODAY, days=14)

        assert history["streak_days"] == 3
        assert history["tests_7d"] == 4
    finally:
        db.query(SessionModel).filter(SessionModel.user_id == USER_ID).delete()
        db.commit()
        db.close()


def test_reviews_count_into_activity_but_not_accuracy(db_factory):
    """Opakovanie nemá odpovede — do úspešnosti vstúpiť nesmie."""
    db = db_factory()
    try:
        db.add(SessionModel(user_id=USER_ID, total=0, correct=0, kind="review",
                            created_at=datetime.combine(TODAY, datetime.min.time())))
        db.commit()

        history = get_history_stats(db, USER_ID, today=TODAY, days=7)

        assert history["reviews_7d"] == 1
        assert history["tests_total"] == 0, "opakovanie nie je test"
        assert history["accuracy_7d"] is None
        assert history["streak_days"] == 1, "opakovanie sa do série dní ráta"
    finally:
        db.query(SessionModel).filter(SessionModel.user_id == USER_ID).delete()
        db.commit()
        db.close()


def test_window_is_long_enough_for_a_yearly_streak():
    """Okno musí pokryť aj dlhú sériu, inak by sa séria zbytočne zlomila."""
    assert HISTORY_WINDOW_DAYS >= 365
