"""Meranie času stráveného v databáze — podklad pre hlavičku `Server-Timing`.

Z vonku sa nedá rozhodnúť, či pomalý endpoint počíta, alebo čaká na databázu.
Rozdiel je pritom zásadný: pri čakaní na DB nepomôže silnejší CPU ani menej
kódu, pomôže menej dotazov alebo bližšia databáza.

Merajú sa všetky dotazy cez `before/after_cursor_execute`, výsledok sa zbiera
do premennej viazanej na požiadavku. Uložený je **meniteľný slovník**, nie
číslo — synchrónne endpointy FastAPI bežia vo vlákne z poolu, ktoré dostane
kópiu kontextu, takže prepísanie premennej by sa k middleware nedostalo, ale
zápis do spoločného slovníka áno.
"""
import time
from contextvars import ContextVar

from sqlalchemy import event

_stats: ContextVar[dict] = ContextVar("db_timing", default=None)


def start_request() -> dict:
    """Založí čisté počítadlo pre práve spracúvanú požiadavku."""
    stats = {"queries": 0, "db_ms": 0.0}
    _stats.set(stats)
    return stats


def current() -> dict:
    return _stats.get()


def install(engine) -> None:
    """Napojí meranie na engine. Volá sa raz pri štarte aplikácie."""

    @event.listens_for(engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):
        conn.info["_query_started"] = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):
        started = conn.info.pop("_query_started", None)
        stats = _stats.get()
        if started is None or stats is None:
            return
        stats["queries"] += 1
        stats["db_ms"] += (time.perf_counter() - started) * 1000
