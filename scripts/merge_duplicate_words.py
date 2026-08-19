"""Jednorazová oprava: zlúči duplicitné heslá v kategóriách do jednej kartičky.

Prečo: AI vygenerovala `subject → téma` aj `subject → predmet` ako dve kartičky
(ukladanie ich odteraz zlúči, ale staré dáta ostali). Používateľ tak dostal to
isté slovo dvakrát s iným „správnym" prekladom a druhý výskyt označil ako
neznámy — odtiaľ „Success: 0 %" pri slovách, ktoré vie.

Čo robí: v rámci jednej kategórie nájde slová s rovnakým heslom (bez ohľadu na
veľkosť písmen a prebytočné medzery), ponechá to s najbohatšou históriou,
pripojí k nemu ostatné preklady ako ďalšie varianty a zvyšné riadky zmaže.
História sa nestráca — počty testov sa spočítajú.

Spustenie (najprv NASUCHO, nič sa nemení):

    python -m scripts.merge_duplicate_words
    python -m scripts.merge_duplicate_words --apply
    python -m scripts.merge_duplicate_words --apply --user-id 1

Potrebuje `DATABASE_URL` v prostredí (rovnako ako aplikácia).
"""
import argparse
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import SessionLocal  # noqa: E402
from app.models.word import Word  # noqa: E402
from app.services.word_dedupe import headword_key, merge_translations  # noqa: E402


def _history(word: Word) -> tuple:
    """Poradie „najbohatšej histórie" — tento riadok prežije zlúčenie."""
    return (word.times_tested or 0, word.times_correct or 0, -(word.id or 0))


def find_duplicate_groups(db, user_id=None):
    """Skupiny riadkov s rovnakým heslom v rámci jednej kategórie."""
    query = db.query(Word)
    if user_id is not None:
        query = query.filter(Word.user_id == user_id)

    buckets = defaultdict(list)
    for word in query.all():
        buckets[(word.user_id, word.category_id, headword_key(word.original_word))].append(word)

    return [rows for rows in buckets.values() if len(rows) > 1]


def merge_group(rows: list):
    """Zlúči skupinu. Vráti (ponechaný, zmazané, výsledný preklad)."""
    rows = sorted(rows, key=_history, reverse=True)
    keeper, rest = rows[0], rows[1:]

    translation = keeper.translation
    for other in rest:
        combined = merge_translations(translation, other.translation)
        if combined:
            translation = combined

    return keeper, rest, translation


def main() -> int:
    parser = argparse.ArgumentParser(description="Zlúči duplicitné heslá v kategóriách.")
    parser.add_argument("--apply", action="store_true",
                        help="Skutočne zapíš zmeny (bez tohto len vypíše, čo by spravil).")
    parser.add_argument("--user-id", type=int, default=None,
                        help="Obmedz na jedného používateľa.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        groups = find_duplicate_groups(db, args.user_id)
        if not groups:
            print("Žiadne duplicitné heslá — niet čo zlučovať.")
            return 0

        deleted_total = 0
        for rows in groups:
            keeper, rest, translation = merge_group(rows)
            deleted_total += len(rest)

            print(f"\nkategória {keeper.category_id} · heslo {keeper.original_word!r}")
            print(f"  ponechá sa  #{keeper.id}: {keeper.translation!r}"
                  f" (testované {keeper.times_tested or 0}×)")
            for other in rest:
                print(f"  zmaže sa    #{other.id}: {other.translation!r}"
                      f" (testované {other.times_tested or 0}×)")
            print(f"  výsledok    {translation!r}")

            if not args.apply:
                continue

            keeper.translation = translation
            # História sa spočíta, aby zlúčenie nevyzeralo ako reset pokroku.
            keeper.times_tested = sum((w.times_tested or 0) for w in rows)
            keeper.times_correct = sum((w.times_correct or 0) for w in rows)
            tested_dates = [w.last_tested for w in rows if w.last_tested]
            if tested_dates:
                keeper.last_tested = max(tested_dates)
            for other in rest:
                db.delete(other)

        if args.apply:
            db.commit()
            print(f"\nHotovo: zlúčených skupín {len(groups)}, zmazaných riadkov {deleted_total}.")
        else:
            print(f"\nNASUCHO: zlúčilo by sa {len(groups)} skupín, zmazalo {deleted_total} riadkov.")
            print("Spusti znova s --apply, ak to takto sedí.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
