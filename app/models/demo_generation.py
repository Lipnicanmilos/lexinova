from app.database.connection import Base
from app.utils import utcnow
from sqlalchemy import Column, DateTime, Integer, String, Text, Index


class DemoGeneration(Base):
    """Sada slovíčok vygenerovaná v ukážke (/demo) pre neprihláseného návštevníka.

    Tabuľka plní dve úlohy naraz:

    1. **Cache** — rovnaká téma sa nikdy negeneruje druhýkrát. Prvý návštevník
       zaplatí AI volanie, každý ďalší dostane hotovú sadu okamžite.
    2. **Počítadlo výdavkov** — riadok tu vznikne LEN pri skutočnom volaní AI,
       takže „koľko riadkov pribudlo dnes" je presne dnešná spotreba ukážky.
       Preto tu nie je samostatná tabuľka s denným počítadlom.

    Slová sú uložené ako JSON text (nie JSONB) — testy bežia na SQLite a čítame
    ich vždy celé naraz, takže dopytovať sa dovnútra nepotrebujeme.
    """
    __tablename__ = "demo_generations"

    id = Column(Integer, primary_key=True, index=True)

    # Normalizovaná téma (malé písmená, bez diakritiky a prebytočných medzier)
    # spolu s jazykovou dvojicou tvorí kľúč cache.
    topic_key = Column(String(120), nullable=False, index=True)
    topic = Column(String(200), nullable=False)
    language_from = Column(String(10), nullable=False, default="en")
    language_to = Column(String(10), nullable=False, default="sk")

    category_name = Column(String(120), nullable=True)
    words_json = Column(Text, nullable=False)

    # Koľkokrát sa sada podávala z cache — podľa toho sa vyberá náhradná sada,
    # keď je denný strop vyčerpaný (obľúbená téma zaujme viac než náhodná).
    hits = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), default=utcnow, index=True)


Index("ix_demo_generations_key", DemoGeneration.topic_key,
      DemoGeneration.language_from, DemoGeneration.language_to)
