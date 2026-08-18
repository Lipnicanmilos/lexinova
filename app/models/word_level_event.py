from app.database.connection import Base
from app.utils import utcnow
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index


class WordLevelEvent(Base):
    """Zmena úrovne znalosti slovíčka v čase.

    Bez tejto histórie vieme len aktuálny stav — koľko slov je „Viem" dnes.
    Riadok tu pribudne LEN keď sa úroveň naozaj zmení (nie pri každom
    zopakovaní karty), takže tabuľka rastie s učením, nie s používaním.

    Odomyká „naučené za posledný týždeň" a krivku učenia v čase.
    """
    __tablename__ = "word_level_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    word_id = Column(Integer, ForeignKey("words.id", ondelete="CASCADE"), nullable=False, index=True)

    # Hodnoty KnowledgeLevel ukladáme ako string — Enum s values_callable inde
    # zapisuje to isté a stringy prežijú aj prípadné premenovanie enumu v kóde.
    level = Column(String(20), nullable=False)
    previous_level = Column(String(20), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow, index=True)


Index("ix_word_level_events_user_created", WordLevelEvent.user_id, WordLevelEvent.created_at)
