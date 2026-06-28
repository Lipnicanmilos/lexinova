"""Spustí SQL migráciu proti databáze z DATABASE_URL (.env).

Použitie (z koreňa projektu, vo venv):
    python scripts/run_migration.py migrations/2026-06-28_add_subscription_columns.sql
    python scripts/run_migration.py migrations/...sql --dry-run   # len vypíše, nespustí

POZOR: pripája sa na DB podľa DATABASE_URL (t.j. produkčná Supabase).
Migrácia je idempotentná (ADD COLUMN IF NOT EXISTS) — dá sa spustiť aj viackrát.
"""
import os
import sys

# Pridaj koreň projektu na sys.path, aby fungoval import `app` aj zo /scripts.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.database.connection import engine


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in sys.argv
    if not args:
        print("Použitie: python scripts/run_migration.py <cesta_k_sql> [--dry-run]")
        sys.exit(1)

    path = args[0]
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()

    # Odstráň komentárové riadky (--) a rozdeľ na jednotlivé príkazy podľa ;
    body = "\n".join(ln for ln in raw.splitlines() if not ln.strip().startswith("--"))
    statements = [s.strip() for s in body.split(";") if s.strip()]

    print(f"Súbor: {path}  ({len(statements)} príkazov){'  [DRY-RUN]' if dry_run else ''}")
    for stmt in statements:
        print("  →", stmt.replace("\n", " ")[:90])

    if dry_run:
        print("Dry-run — nič sa nespustilo.")
        return

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
    print("✅ Migrácia úspešne spustená.")


if __name__ == "__main__":
    main()
