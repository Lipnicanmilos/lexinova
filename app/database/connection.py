# app/database/connection.py
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Database URL - must be set in .env for PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable must be set (use PostgreSQL URL from Supabase)")

# pool_pre_ping: Supabase/Cloud Run zatvárajú idle spojenia — bez pingu by
# prvý request po pauze dostal "server closed the connection unexpectedly".
# Dávkové zápisy (napr. výsledky testu) posiela psycopg2 predvolene po jednom
# riadku. `values_plus_batch` ich pošle naraz — pri vzdialenej databáze je to
# rozdiel medzi jednou cestou a jednou na každé slovíčko. Parameter je špecifický
# pre psycopg2, takže pri SQLite (testy) sa nepridáva.
_engine_kwargs = {"pool_pre_ping": True, "pool_recycle": 1800}
if DATABASE_URL.startswith("postgresql"):
    _engine_kwargs["executemany_mode"] = "values_plus_batch"

engine = create_engine(DATABASE_URL, **_engine_kwargs)

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