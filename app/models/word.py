from app.database.connection import Base
from app.utils import utcnow
from sqlalchemy import Column, Integer, String, DateTime, Enum, Float, ForeignKey, Index
import enum

EXAMPLE_MAX_LENGTH = 300


def clean_example(value) -> str | None:
    """Veta z AI alebo z formulára → text do stĺpca. Prázdne a nezmysly dajú
    None, pridlhá veta sa oreže (Postgres by na nej inak zhodil celý zápis)."""
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    return text[:EXAMPLE_MAX_LENGTH] or None


class KnowledgeLevel(enum.Enum):
    DONT_KNOW = "dont_know"
    LEARNING = "learning"
    KNOW = "know"

class Word(Base):
    __tablename__ = "words"
    
    id = Column(Integer, primary_key=True, index=True)
    original_word = Column(String(100), nullable=False)
    translation = Column(String(100), nullable=False)
    language_from = Column(String(10), default="en")
    language_to = Column(String(10), default="sk")
    # Oba stĺpce sú indexované: statistiky aj zoznamy slov filtrujú výhradne
    # cez user_id, kategória cez category_id. Postgres si index nad cudzím
    # kľúčom sám nevytvorí, takže bez nich šiel každý dotaz seq scanom.
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, nullable=True, index=True)

    # Príkladová veta v jazyku slova (language_from) a jej preklad. Nepovinné:
    # ručne pridané a importované slová ju nemajú, kým si ju používateľ nedá
    # dogenerovať. Dĺžku stráži EXAMPLE_MAX_LENGTH aj na vstupe z AI.
    example_sentence = Column(String(300), nullable=True)
    example_translation = Column(String(300), nullable=True)

    # Pokročilé polia pre testovanie
    knowledge_level = Column(Enum(KnowledgeLevel, values_callable=lambda x: [e.value for e in x]), default=KnowledgeLevel.DONT_KNOW)
    times_tested = Column(Integer, default=0)
    times_correct = Column(Integer, default=0)
    last_tested = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


# Štatistiky filtrujú user_id spolu s times_tested/last_tested — zložený index
# pokryje „netestované" aj „dávno netestované" jedným prechodom.
Index("ix_words_user_tested", Word.user_id, Word.times_tested)
