from app.database.connection import Base
from app.models.word import KnowledgeLevel
from app.utils import utcnow
from sqlalchemy import Column, Integer, DateTime, Enum, ForeignKey, UniqueConstraint


class WordProgress(Base):
    """Per-user pokrok na cudzom slove (sady triedy sú live odkaz na učiteľove
    Word riadky, takže pokrok žiaka nemôže žiť na Word stĺpcoch).

    Vlastné slová ďalej používajú stĺpce priamo na Word — táto tabuľka sa
    použije len keď testovaný Word nepatrí prihlásenému userovi.
    V DB je knowledge_level VARCHAR (Enum s values_callable ukladá stringy).
    """
    __tablename__ = "word_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "word_id", name="uq_word_progress_user_word"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    word_id = Column(Integer, ForeignKey("words.id", ondelete="CASCADE"), nullable=False, index=True)

    knowledge_level = Column(Enum(KnowledgeLevel, values_callable=lambda x: [e.value for e in x]), default=KnowledgeLevel.DONT_KNOW)
    times_tested = Column(Integer, default=0)
    times_correct = Column(Integer, default=0)
    last_tested = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
