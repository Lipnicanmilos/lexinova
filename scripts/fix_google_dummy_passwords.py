"""Jednorazová oprava: nahradí konštantné Google OAuth dummy heslo náhodným.

Účty vytvorené cez Google OAuth dostávali bcrypt hash konštantného stringu
"google_auth_dummy_password" — ktokoľvek so znalosťou e-mailu sa nimi vedel
prihlásiť cez /api/v1/login. Tento skript prejde všetkých užívateľov, overí
hash proti dummy stringu a postihnutým nastaví náhodné heslo, ktoré nikto
nepozná (Google užívateľ sa prihlasuje cez OAuth; lokálne heslo si vie
nastaviť cez forgot-password).

Použitie (z koreňa projektu, vo venv):
    python scripts/fix_google_dummy_passwords.py --dry-run   # len vypíše počty
    python scripts/fix_google_dummy_passwords.py             # opraví

POZOR: pripája sa na DB podľa DATABASE_URL (t.j. produkčná Supabase).
Skript je idempotentný — po oprave už žiadny hash dummy stringu nesedí.
"""
import os
import secrets
import sys

# Pridaj koreň projektu na sys.path, aby fungoval import `app` aj zo /scripts.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import SessionLocal
from app.models.category import Category  # noqa: F401  (registrácia pre User.categories relationship)
from app.models.word import Word  # noqa: F401  (registrácia pre Category.words relationship)
from app.models.user import User
from app.services.auth_service import hash_password, verify_password

DUMMY_PASSWORD = "google_auth_dummy_password"


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    db = SessionLocal()
    try:
        users = db.query(User).all()
        affected = []
        for user in users:
            try:
                if verify_password(DUMMY_PASSWORD, user.password):
                    affected.append(user)
            except ValueError:
                # iný formát hashu (napr. argon2 z minulosti) — nie je dummy
                continue

        print(f"Užívateľov spolu: {len(users)}, s dummy heslom: {len(affected)}"
              f"{'  [DRY-RUN]' if dry_run else ''}")
        for user in affected:
            print(f"  → id={user.id} {user.email}")

        if dry_run or not affected:
            print("Nič sa nezmenilo." if dry_run or not affected else "")
            return

        for user in affected:
            user.password = hash_password(secrets.token_urlsafe(32))
        db.commit()
        print(f"✅ Opravených {len(affected)} účtov (náhodné heslo).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
