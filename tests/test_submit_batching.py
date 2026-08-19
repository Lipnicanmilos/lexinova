"""Ukladanie výsledkov testu nesmie chodiť do databázy po jednom slove.

Nález používateľa 2026-08-19: „skončím kartičky, vrátim sa na nástenku a čísla
musím aktualizovať viackrát, kým sú správne." Endpoint načítaval každé slovo
vlastným dotazom a zapisoval ho vlastným UPDATE-om — pri 21 kartičkách to bolo
vyše 40 ciest do databázy, čo je nad vzdialenou DB (~112 ms na cestu) niekoľko
sekúnd. Odchod na nástenku čaká na uloženie najviac 5 s, takže sa dashboard
stihol načítať skôr, než zápis dobehol.

Test stráži počet príkazov, nie čas — čas závisí od siete, počet ciest od kódu.
"""
from sqlalchemy import event

from app.models.category import Category
from app.models.user import User
from app.models.word import KnowledgeLevel, Word
from app.routers.words import submit_test_results
# Alias — pytest by inak schemu TestResult zbieral ako testovaciu triedu (prefix "Test").
from app.schemas.word import TestResult as Answer


def _seed(db, email, count=21):
    user = User(email=email, password="x", name="T")
    db.add(user)
    db.commit()
    db.refresh(user)

    category = Category(name="Sada", user_id=user.id)
    db.add(category)
    db.commit()
    db.refresh(category)

    for i in range(count):
        db.add(Word(
            original_word=f"w{i}", translation=f"p{i}",
            category_id=category.id, user_id=user.id,
            knowledge_level=KnowledgeLevel.DONT_KNOW, times_tested=0, times_correct=0,
        ))
    db.commit()
    return user, db.query(Word).filter(Word.user_id == user.id).all()


def test_submit_writes_all_words_in_one_update(db_factory):
    db = db_factory()
    try:
        user, words = _seed(db, "batch1@example.com")
        results = [Answer(word_id=w.id, is_correct=(i % 2 == 0))
                   for i, w in enumerate(words)]

        statements = []
        engine = db.get_bind()

        @event.listens_for(engine, "before_cursor_execute")
        def _collect(conn, cursor, statement, params, context, executemany):
            statements.append(statement.strip().split()[0].upper())

        try:
            submit_test_results(results=results, db=db, current_user=user)
        finally:
            event.remove(engine, "before_cursor_execute", _collect)

        updates = statements.count("UPDATE")
        selects = statements.count("SELECT")
        assert updates == 1, f"21 kartičiek = 1 UPDATE, nie {updates}"
        assert selects <= 5, f"slová sa majú načítať naraz, nie po jednom ({selects} SELECTov)"
    finally:
        db.query(Word).delete()
        db.query(Category).delete()
        db.commit()
        db.close()


def test_submit_still_records_progress_correctly(db_factory):
    """Hromadný zápis nesmie nič stratiť ani započítať dvakrát."""
    db = db_factory()
    try:
        user, words = _seed(db, "batch2@example.com", count=4)
        results = [Answer(word_id=w.id, is_correct=(i < 3)) for i, w in enumerate(words)]

        submit_test_results(results=results, db=db, current_user=user)

        rows = db.query(Word).filter(Word.user_id == user.id).order_by(Word.id).all()
        assert [w.times_tested for w in rows] == [1, 1, 1, 1]
        assert [w.times_correct for w in rows] == [1, 1, 1, 0]
        assert [w.knowledge_level for w in rows] == [
            KnowledgeLevel.KNOW, KnowledgeLevel.KNOW, KnowledgeLevel.KNOW, KnowledgeLevel.DONT_KNOW,
        ]
        assert all(w.last_tested is not None for w in rows)
    finally:
        db.query(Word).delete()
        db.query(Category).delete()
        db.commit()
        db.close()
