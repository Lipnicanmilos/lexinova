"""Overovanie spojenia stálo round-trip na každom requeste.

`pool_pre_ping=True` posiela `SELECT 1` pred každým vypožičaním spojenia — nad
vzdialenou databázou (~112 ms na cestu) je to daň platená aj vtedy, keď to isté
spojenie odišlo pred sekundou. Ping teraz beží len po nečinnosti; táto hranica
je to jediné, čo stojí medzi rýchlosťou a chybou „server closed the connection".
"""
import time

from sqlalchemy import create_engine, text

import app.database.connection as conn_module


def test_engine_does_not_ping_on_every_checkout():
    """Zapnutý pool_pre_ping by vrátil starý stav bez toho, aby čokoľvek spadlo."""
    assert conn_module.engine.pool._pre_ping is False, (
        "pool_pre_ping je späť — každý request opäť platí SELECT 1 navyše"
    )


def test_idle_threshold_is_short_enough_to_be_safe():
    """Príliš dlhá hranica = prvý request po pauze spadne na mŕtvom spojení."""
    assert 5 <= conn_module.PING_AFTER_IDLE_SECONDS <= 120


def test_fresh_connection_is_reused_without_a_ping(monkeypatch):
    """Dve operácie za sebou nesmú poslať kontrolný dotaz."""
    engine = create_engine("sqlite://")
    conn_module.PING_AFTER_IDLE_SECONDS  # hranica sa berie z modulu

    pings = []

    # Rovnaká dvojica poslucháčov ako v aplikácii, len nad testovacím enginom.
    from sqlalchemy import event
    from sqlalchemy.exc import DisconnectionError

    @event.listens_for(engine, "checkin")
    def _remember(dbapi_connection, record):
        record.info["returned_at"] = time.monotonic()

    @event.listens_for(engine, "checkout")
    def _ping(dbapi_connection, record, proxy):
        returned_at = record.info.get("returned_at")
        if returned_at is not None and (time.monotonic() - returned_at) < 30:
            return
        pings.append(1)
        try:
            cur = dbapi_connection.cursor()
            cur.execute("SELECT 1")
            cur.close()
        except Exception as exc:
            raise DisconnectionError() from exc

    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    assert len(pings) == 1, "prvé vypožičanie spojenie overí"

    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    assert len(pings) == 1, "hneď vrátené spojenie sa už neoveruje"
