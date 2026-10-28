"""AI tútor s pamäťou — rozhovory, ktoré si server pamätá naprieč reláciami.

Na rozdiel od rozhovoru nad sadou (`ai_chat`, server si nič nepamätá) tu
ukladáme štyri veci:

- **TutorProfile** — jeden riadok na používateľa: úroveň, čo o sebe povedal
  (záujmy, ciele, práca), jeho typické chyby. Prepisuje ho AI po každej relácii.
- **TutorSession** — jeden rozhovor; po ukončení dostane súhrn.
- **TutorMessage** — jednotlivé správy rozhovoru.
- **TutorMemory** — „spomienky" s vektorom (embedding). Pri každej správe sa
  vyhľadajú tie, ktoré sa jej významom najviac podobajú, a vložia sa AI do pokynov.

Vektor: na Postgrese (Supabase) stĺpec `vector(768)` z rozšírenia pgvector,
hľadanie cez operátor kosínusovej vzdialenosti `<=>`. Testy bežia na SQLite —
tam je to text `[0.1, …]` a vzdialenosť sa počíta v Pythone (`tutor_memory`).
"""
import json
from typing import List, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.types import TypeDecorator, UserDefinedType

from app.database.connection import Base
from app.utils import utcnow

EMBEDDING_DIM = 768


class _PgVector(UserDefinedType):
    """`vector(N)` z pgvector — bez závislosti na balíku `pgvector`.

    Hodnotu posielame ako text `[a,b,…]`; Postgres ho do `vector` pretypuje sám."""
    cache_ok = True

    def __init__(self, dim: int):
        self.dim = dim

    def get_col_spec(self, **kw):
        return f"vector({self.dim})"


class Embedding(TypeDecorator):
    """Zoznam floatov ↔ `vector(768)` na Postgrese, text na SQLite."""
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(_PgVector(EMBEDDING_DIM))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: Optional[List[float]], dialect):
        if value is None:
            return None
        return "[" + ",".join(f"{float(x):.7g}" for x in value) + "]"

    def process_result_value(self, value, dialect) -> Optional[List[float]]:
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return [float(x) for x in value]
        return [float(x) for x in json.loads(value)]


class TutorProfile(Base):
    __tablename__ = "tutor_profiles"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    # Úroveň CEFR, ktorú si zvolil používateľ alebo odhadla AI po relácii.
    level = Column(String(4), nullable=False, default="A2")
    # Jazyk, ktorý sa učí, a jeho materinský jazyk (kódy ako pri slovíčkach).
    language_from = Column(String(10), nullable=False, default="en")
    language_to = Column(String(10), nullable=False, default="sk")
    # Čo AI o používateľovi vie — krátke odrážky, ktoré po každej relácii prepíše.
    facts = Column(Text, nullable=True)
    # Opakujúce sa chyby, na ktoré sa má AI zamerať.
    mistakes = Column(Text, nullable=True)
    sessions_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class TutorSession(Base):
    __tablename__ = "tutor_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at = Column(DateTime, default=utcnow, nullable=False)
    # NULL = relácia ešte nie je zhrnutá (beží, alebo ju používateľ len zavrel —
    # zhrnie sa pri ďalšom štarte).
    ended_at = Column(DateTime, nullable=True)
    summary = Column(Text, nullable=True)
    user_messages = Column(Integer, nullable=False, default=0)


class TutorMessage(Base):
    __tablename__ = "tutor_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("tutor_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(10), nullable=False)  # "user" / "assistant"
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class TutorMemory(Base):
    __tablename__ = "tutor_memories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("tutor_sessions.id", ondelete="SET NULL"), nullable=True)
    kind = Column(String(16), nullable=False)  # summary / fact / mistake
    text = Column(Text, nullable=False)
    # NULL = embedding sa nepodaril (výpadok Gemini). Spomienka sa potom
    # nájde len medzi najnovšími, nie podľa významu.
    embedding = Column(Embedding, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)


Index("ix_tutor_messages_session_created", TutorMessage.session_id, TutorMessage.created_at)
Index("ix_tutor_memories_user_created", TutorMemory.user_id, TutorMemory.created_at)
