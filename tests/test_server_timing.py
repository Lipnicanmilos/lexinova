"""Hlavička Server-Timing — rozdelenie času požiadavky na databázu a appku.

Zvonku sa nedá povedať, či je endpoint pomalý výpočtom, alebo čakaním na DB.
Tieto testy overujú, že rozdelenie naozaj vzniká a dostane sa do odpovede.
"""
from sqlalchemy import create_engine, text

from app.services import timing


def test_header_is_present_and_parsable(client):
    res = client.get("/robots.txt")
    header = res.headers.get("Server-Timing")

    assert header, "Server-Timing chýba — bez neho sa meranie nedá rozdeliť"
    for metric in ("db;dur=", "app;dur=", "total;dur="):
        assert metric in header
    assert "queries" in header


def test_db_time_and_query_count_are_measured():
    """Listenery musia rátať skutočné dotazy, nie odhad."""
    engine = create_engine("sqlite://")
    timing.install(engine)
    stats = timing.start_request()

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        conn.execute(text("SELECT 2"))

    assert stats["queries"] == 2
    assert stats["db_ms"] >= 0


def test_counter_is_per_request():
    """Nová požiadavka začína od nuly — inak by čísla naprieč requestami rástli."""
    first = timing.start_request()
    first["queries"] = 5

    second = timing.start_request()
    assert second["queries"] == 0
    assert first is not second
