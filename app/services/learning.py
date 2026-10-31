"""Jedno učenie: výber slov na dnes a úloha ku každému z nich.

Používateľ si nevyberá sadu, skupinu slov ani režim. Server vezme, čo je na rade
(naprieč sadami, so zámkom free účtu), a ku každému slovu zvolí úlohu podľa toho,
ako dobre ho už vie: nové slovo sa ukáže na kartičke, potom sa z neho stáva výber
významu, dopĺňanie do vety a počúvanie.

Slová z vlastných sád majú pokrok na `words`, slová zo sád tried na
`word_progress` (patria učiteľovi). Obidve cesty sa tu spájajú do `Entry`.
Nad vzdialenou databázou platíme za počet dotazov, preto ani jeden nie je v cykle.
"""
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.school_class import ClassCategory, ClassMember
from app.models.user import User
from app.models.word import Word
from app.models.word_progress import WordProgress
from app.services.cloze import ClozePools, build_task, is_phrase, pick_options
from app.utils import utcnow

# Koľko slov má jedno učenie (asi štyri minúty).
SESSION_SIZE = 12

CARD = "card"
CHOICE = "choice"
CLOZE = "cloze"
LISTEN = "listen"


@dataclass
class Scope:
    """Z čoho sa smie vyberať. `own_ids` None = všetky vlastné sady (PLUS)."""
    own_ids: Optional[list]
    class_ids: list


@dataclass
class Entry:
    word: Word
    box: int
    due_at: Optional[datetime]
    last_tested: Optional[datetime]


def _class_category_ids(db: Session, user_id: int) -> list:
    rows = (
        db.query(ClassCategory.category_id)
        .join(ClassMember, ClassMember.class_id == ClassCategory.class_id)
        .join(Category, Category.id == ClassCategory.category_id)
        .filter(ClassMember.user_id == user_id, Category.user_id != user_id)
        .distinct()
        .all()
    )
    return [row[0] for row in rows]


def _newest_own_category_id(db: Session, user_id: int) -> Optional[int]:
    row = (
        db.query(Category.id)
        .filter(Category.user_id == user_id)
        .order_by(Category.created_at.desc())
        .first()
    )
    return row[0] if row else None


def user_scope(db: Session, user: User) -> Scope:
    """Všetko, čo sa používateľ smie učiť. Free účet má odomknutú len najnovšiu
    vlastnú sadu, sady triedy vždy — rovnako ako `_check_category_access`."""
    own_ids = None
    if not user.is_plus:
        newest = _newest_own_category_id(db, user.id)
        own_ids = [newest] if newest is not None else []
    return Scope(own_ids=own_ids, class_ids=_class_category_ids(db, user.id))


def category_scope(db: Session, user: User, category_id: int) -> Scope:
    """Učenie jednej sady, so zámkom free účtu."""
    owner = db.query(Category.user_id).filter(Category.id == category_id).first()
    if owner is None:
        raise HTTPException(status_code=404, detail="Category not found")
    if owner[0] == user.id:
        if not user.is_plus and _newest_own_category_id(db, user.id) != category_id:
            raise HTTPException(status_code=403, detail="Táto sada je zamknutá. Odomkne ju PLUS.")
        return Scope(own_ids=[category_id], class_ids=[])
    if category_id not in _class_category_ids(db, user.id):
        raise HTTPException(status_code=404, detail="Category not found")
    return Scope(own_ids=[], class_ids=[category_id])


def _own_filter(query, user_id: int, scope: Scope):
    query = query.filter(Word.user_id == user_id)
    if scope.own_ids is not None:
        query = query.filter(Word.category_id.in_(scope.own_ids))
    return query


def _class_join(query, user_id: int, scope: Scope):
    return query.outerjoin(
        WordProgress, and_(WordProgress.word_id == Word.id, WordProgress.user_id == user_id)
    ).filter(Word.category_id.in_(scope.class_ids))


def _has_own(scope: Scope) -> bool:
    return scope.own_ids is None or bool(scope.own_ids)


def get_today_summary(db: Session, user: User, now: Optional[datetime] = None) -> dict:
    """Koľko slov je na rade a koľko nových čaká — pre obrazovku Dnes."""
    now = now or utcnow()
    scope = user_scope(db, user)
    due = new = 0
    if _has_own(scope):
        row = _own_filter(
            db.query(
                func.count(case((Word.due_at <= now, 1))),
                func.count(case((Word.due_at.is_(None), 1))),
            ),
            user.id, scope,
        ).one()
        due, new = int(row[0] or 0), int(row[1] or 0)
    if scope.class_ids:
        row = _class_join(
            db.query(
                func.count(case((WordProgress.due_at <= now, 1))),
                func.count(case((WordProgress.due_at.is_(None), 1))),
            ).select_from(Word),
            user.id, scope,
        ).one()
        due += int(row[0] or 0)
        new += int(row[1] or 0)
    return {"due": due, "new": new, "session_size": SESSION_SIZE}


def _null_last(column):
    """NULL na koniec zoradenia — Postgres a SQLite ho inak radia každý inde."""
    return case((column.is_(None), 1), else_=0)


def _null_first(column):
    return case((column.is_(None), 0), else_=1)


def select_entries(
    db: Session, user: User, scope: Scope, extra: bool = False,
    size: int = SESSION_SIZE, now: Optional[datetime] = None,
) -> list:
    """Slová do jedného učenia.

    Najprv, čo je na rade (najstarší termín prvý), voľné miesta doplnia nové
    slová — z najnovšej sady, v poradí, v akom v nej stoja. `extra` je učenie
    navyše: čo si používateľ najdlhšie neskúšal, bez ohľadu na termín.
    """
    now = now or utcnow()
    entries: list[Entry] = []

    if _has_own(scope):
        query = _own_filter(db.query(Word), user.id, scope)
        if extra:
            query = query.order_by(_null_first(Word.last_tested), Word.last_tested, Word.id)
        else:
            query = query.filter(or_(Word.due_at <= now, Word.due_at.is_(None))).order_by(
                _null_last(Word.due_at), Word.due_at, Word.category_id.desc(), Word.id
            )
        for word in query.limit(size).all():
            entries.append(Entry(word, word.box or 0, word.due_at, word.last_tested))

    if scope.class_ids:
        query = _class_join(db.query(Word, WordProgress), user.id, scope)
        if extra:
            query = query.order_by(
                _null_first(WordProgress.last_tested), WordProgress.last_tested, Word.id
            )
        else:
            query = query.filter(
                or_(WordProgress.due_at <= now, WordProgress.due_at.is_(None))
            ).order_by(
                _null_last(WordProgress.due_at), WordProgress.due_at,
                Word.category_id.desc(), Word.id,
            )
        for word, progress in query.limit(size).all():
            entries.append(Entry(
                word,
                (progress.box or 0) if progress else 0,
                progress.due_at if progress else None,
                progress.last_tested if progress else None,
            ))

    if extra:
        entries.sort(key=lambda e: (e.last_tested is not None, e.last_tested or now))
    else:
        entries.sort(key=lambda e: (e.due_at is None, e.due_at or now, -e.word.category_id, e.word.id))
    return entries[:size]


@dataclass
class CategoryPools:
    """Z čoho sa v jednej sade berú nesprávne možnosti."""
    cloze: ClozePools
    plain_translations: list
    phrase_translations: list

    def translations_like(self, headword: str) -> list:
        """Preklady rovnakého druhu: pri fráze frázy, pri slove slová —
        jedna veta medzi slovami by sa dala uhádnuť na prvý pohľad."""
        own = self.phrase_translations if is_phrase(headword) else self.plain_translations
        return own or (self.plain_translations + self.phrase_translations)

    def headwords_like(self, headword: str) -> list:
        if is_phrase(headword):
            phrases = [w for w in self.cloze.headwords if is_phrase(w)]
            return phrases or self.cloze.headwords
        return self.cloze.plain or self.cloze.headwords


def load_pools(db: Session, category_ids: set) -> dict:
    """Heslá a preklady všetkých dotknutých sád jedným dotazom."""
    if not category_ids:
        return {}
    grouped: dict = {}
    rows = (
        db.query(Word.category_id, Word.original_word, Word.translation)
        .filter(Word.category_id.in_(category_ids))
        .all()
    )
    for category_id, original, translation in rows:
        grouped.setdefault(category_id, []).append((original, translation))
    return {
        category_id: CategoryPools(
            cloze=ClozePools.from_headwords([o for o, _ in pairs]),
            plain_translations=[t for o, t in pairs if not is_phrase(o)],
            phrase_translations=[t for o, t in pairs if is_phrase(o)],
        )
        for category_id, pairs in grouped.items()
    }


def pick_exercise(box: int, can_choose: bool, can_cloze: bool, rng=random) -> str:
    """Čím lepšie slovo vieš, tým ťažšia úloha.

    Nové slovo treba najprv uvidieť, až potom ho spoznať medzi možnosťami,
    použiť vo vete a nakoniec spoznať sluchom. Keď v sade niet z čoho skladať
    možnosti, ostáva kartička.
    """
    if box <= 0 or not can_choose:
        return CARD
    if box == 1:
        return CHOICE
    if box == 2:
        return CLOZE if can_cloze else CHOICE
    return rng.choice([LISTEN, CLOZE] if can_cloze else [LISTEN, CHOICE])


def build_item(entry: Entry, pools: Optional[CategoryPools], rng=random) -> dict:
    word = entry.word
    item = {
        "id": word.id,
        "exercise": CARD,
        "original_word": word.original_word,
        "translation": word.translation,
        "language_from": word.language_from,
        "language_to": word.language_to,
        "example_sentence": word.example_sentence,
        "example_translation": word.example_translation,
    }
    if not pools:
        return item

    choice_options = pick_options(word.translation, pools.translations_like(word.original_word), rng)
    listen_options = pick_options(word.original_word, pools.headwords_like(word.original_word), rng)
    task = build_task(
        word.original_word, word.translation, word.example_sentence, word.example_translation,
        pools.cloze, rng,
    )
    exercise = pick_exercise(entry.box, bool(choice_options and listen_options), bool(task), rng)
    item["exercise"] = exercise
    if exercise == CHOICE:
        item.update(options=choice_options, answer=word.translation)
    elif exercise == LISTEN:
        item.update(options=listen_options, answer=word.original_word)
    elif exercise == CLOZE:
        item.update(
            options=task.options, answer=task.answer,
            sentence_before=task.before, sentence_hidden=task.hidden, sentence_after=task.after,
            sentence_translation=task.translation,
        )
    return item


def build_session(
    db: Session, user: User, category_id: Optional[int] = None, extra: bool = False, rng=random
) -> list:
    """Hotové úlohy na jedno učenie, v premiešanom poradí.

    Sada otvorená zo stránky sady sa dá učiť vždy: keď v nej nič nie je na rade,
    prejde sa do učenia navyše. Obrazovka Dnes tak nerobí — tam prázdna dávka
    znamená „na dnes hotovo".
    """
    scope = category_scope(db, user, category_id) if category_id else user_scope(db, user)
    entries = select_entries(db, user, scope, extra=extra)
    if not entries and category_id:
        entries = select_entries(db, user, scope, extra=True)
    pools = load_pools(db, {e.word.category_id for e in entries})
    items = [build_item(e, pools.get(e.word.category_id), rng) for e in entries]
    rng.shuffle(items)
    return items
