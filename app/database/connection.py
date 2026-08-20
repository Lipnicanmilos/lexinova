# app/database/connection.py
import time

from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import DisconnectionError
from sqlalchemy.orm import declarative_base, sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Database URL - must be set in .env for PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable must be set (use PostgreSQL URL from Supabase)")

# Dávkové zápisy (napr. výsledky testu) posiela psycopg2 predvolene po jednom
# riadku. `values_plus_batch` ich pošle naraz — pri vzdialenej databáze je to
# rozdiel medzi jednou cestou a jednou na každé slovíčko. Parameter je špecifický
# pre psycopg2, takže pri SQLite (testy) sa nepridáva.
#
# `pool_pre_ping` zámerne NIE JE zapnutý — posielal by `SELECT 1` pred každým
# vypožičaním spojenia, čo je pri vzdialenej databáze ~112 ms na každý request.
# Namiesto toho pingáme len spojenie, ktoré chvíľu ležalo (nižšie).
_engine_kwargs = {"pool_recycle": 1800}
if DATABASE_URL.startswith("postgresql"):
    _engine_kwargs["executemany_mode"] = "values_plus_batch"

engine = create_engine(DATABASE_URL, **_engine_kwargs)

# Po akej dobe nečinnosti sa spojenie pred použitím overí. Spojenia umierajú, keď
# Cloud Run uspí inštanciu alebo Supabase zavrie nečinné spojenie — nie medzi
# dvoma requestami za sebou.
PING_AFTER_IDLE_SECONDS = 30


@event.listens_for(engine, "checkin")
def _remember_checkin(dbapi_connection, connection_record):
    connection_record.info["returned_at"] = time.monotonic()


@event.listens_for(engine, "checkout")
def _ping_stale_connection(dbapi_connection, connection_record, connection_proxy):
    """Overenie spojenia len keď má zmysel — inak je to round-trip navyše.

    Pri mŕtvom spojení vyhodíme `DisconnectionError`; SQLAlchemy ho zahodí,
    otvorí nové a operáciu zopakuje. To isté robí `pool_pre_ping`, len bez
    tejto podmienky.
    """
    returned_at = connection_record.info.get("returned_at")
    if returned_at is not None and (time.monotonic() - returned_at) < PING_AFTER_IDLE_SECONDS:
        return
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
    except Exception as exc:
        raise DisconnectionError("spojenie je mŕtve, otváram nové") from exc

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class
Base = declarative_base()

# Funkcia pre získanie DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()