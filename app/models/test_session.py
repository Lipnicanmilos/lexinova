from app.database.connection import Base
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship


class TestSession(Base):
    """Jeden absolvovaný test kartičiek.

    Slúži ako história v čase — odomyká streak (séria dní), grafy aktivity,
    krivku úspešnosti a gamifikáciu. Jeden riadok = jedno odoslanie výsledkov
    testu (`POST /api/v1/words/test/submit`).
    """
    __tablename__ = "test_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # Kategória, z ktorej test bol (ak išlo o jednu); NULL = naprieč kategóriami / zmazaná
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)

    total = Column(Integer, default=0, nullable=False)     # počet kariet v teste
    correct = Column(Integer, default=0, nullable=False)   # koľko z nich „viem"

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    user = relationship("User", backref="test_sessions")


Index("ix_test_sessions_user_created", TestSession.user_id, TestSession.created_at)
