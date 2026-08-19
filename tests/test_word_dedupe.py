"""Duplicitné heslá — jedna kartička s viacerými prekladmi namiesto dvoch kariet.

Pôvodná chyba: `subject → téma` aj `subject → predmet` skončili ako dva riadky,
lebo session má `autoflush=False` a kontrolný dotaz neuložené slovo z tej istej
dávky nevidel. Používateľ potom to isté slovo dostal dvakrát.
"""
from app.models.category import Category
from app.models.word import Word
from app.services.word_dedupe import headword_key, merge_translations
from scripts.merge_duplicate_words import find_duplicate_groups, merge_group


# ── Kľúč hesla ──

def test_headword_key_ignores_case_and_spacing():
    assert headword_key("Subject") == headword_key("subject") == "subject"
    assert headword_key("  speak   proudly ") == "speak proudly"


def test_headword_key_keeps_diacritics():
    """„šport" a „sport" sú dve rôzne slová — zlúčiť ich by bola chyba."""
    assert headword_key("šport") != headword_key("sport")


# ── Zlučovanie prekladov ──

def test_merge_adds_second_meaning():
    assert merge_translations("téma", "predmet") == "téma, predmet"


def test_merge_skips_variant_already_present():
    assert merge_translations("téma, predmet", "Predmet") is None
    assert merge_translations("téma", "téma") is None


def test_merge_refuses_to_overflow_column():
    """Preklad je VARCHAR(100) — dlhší reťazec by databáza odmietla."""
    existing = "a" * 95
    assert merge_translations(existing, "bbbbbbbbbb") is None


def test_merge_ignores_empty_incoming():
    assert merge_translations("téma", "   ") is None


# ── Ukladanie AI výstupu ──

def _ai_payload(words):
    return {
        "category_name": "Lekcia",
        "category_description": None,
        "words": [
            {"original_word": o, "translation": t, "language_from": "en", "language_to": "sk"}
            for o, t in words
        ],
    }


def _persist(db, user_id, payload):
    from app.routers.categories import _persist_generated_category
    from app.models.user import User

    user = db.query(User).filter(User.id == user_id).first()
    return _persist_generated_category(db, user, payload, "en", "sk", None)


def _make_user(db, email):
    from app.models.user import User

    user = User(email=email, password="x", name="T")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_same_headword_twice_in_one_batch_becomes_one_card(db_factory):
    db = db_factory()
    try:
        user = _make_user(db, "dedupe1@example.com")
        res = _persist(db, user.id, _ai_payload([
            ("subject", "téma"),
            ("speak proudly", "hovoriť hrdo"),
            ("subject", "predmet"),          # to isté heslo, iný preklad
        ]))

        words = db.query(Word).filter(Word.user_id == user.id).all()
        assert len(words) == 2, "duplicitné heslo nesmie vyrobiť druhú kartičku"
        subject = next(w for w in words if w.original_word == "subject")
        assert subject.translation == "téma, predmet"
        assert res.inserted_words == 2
    finally:
        db.query(Word).delete()
        db.query(Category).delete()
        db.commit()
        db.close()


def test_case_differing_headword_is_the_same_word(db_factory):
    db = db_factory()
    try:
        user = _make_user(db, "dedupe2@example.com")
        _persist(db, user.id, _ai_payload([("border", "hranica"), ("Border", "okraj")]))

        words = db.query(Word).filter(Word.user_id == user.id).all()
        assert len(words) == 1
        assert words[0].translation == "hranica, okraj"
    finally:
        db.query(Word).delete()
        db.query(Category).delete()
        db.commit()
        db.close()


def test_second_generation_adds_meaning_instead_of_overwriting(db_factory):
    """Opakované generovanie do tej istej kategórie nesmie prepísať preklad."""
    db = db_factory()
    try:
        user = _make_user(db, "dedupe3@example.com")
        _persist(db, user.id, _ai_payload([("subject", "téma")]))
        _persist(db, user.id, _ai_payload([("subject", "predmet")]))

        words = db.query(Word).filter(Word.user_id == user.id).all()
        assert len(words) == 1
        assert words[0].translation == "téma, predmet"
    finally:
        db.query(Word).delete()
        db.query(Category).delete()
        db.commit()
        db.close()


# ── Oprava existujúcich dát ──

def test_cleanup_script_merges_and_keeps_history(db_factory):
    db = db_factory()
    try:
        user = _make_user(db, "dedupe4@example.com")
        category = Category(name="Stará lekcia", user_id=user.id)
        db.add(category)
        db.commit()
        db.refresh(category)

        keep = Word(original_word="subject", translation="téma", category_id=category.id,
                    user_id=user.id, times_tested=3, times_correct=1)
        dupe = Word(original_word="Subject", translation="predmet", category_id=category.id,
                    user_id=user.id, times_tested=1, times_correct=0)
        solo = Word(original_word="gate", translation="brána", category_id=category.id,
                    user_id=user.id)
        db.add_all([keep, dupe, solo])
        db.commit()

        groups = find_duplicate_groups(db, user.id)
        assert len(groups) == 1, "osamotené slovo sa nesmie tváriť ako duplicita"

        keeper, rest, translation = merge_group(groups[0])
        assert keeper.id == keep.id, "prežiť má riadok s bohatšou históriou"
        assert [w.id for w in rest] == [dupe.id]
        assert translation == "téma, predmet"
    finally:
        db.query(Word).delete()
        db.query(Category).delete()
        db.commit()
        db.close()
