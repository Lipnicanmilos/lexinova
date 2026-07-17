from app.database.connection import Base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import backref, relationship


class SchoolClass(Base):
    """Trieda učiteľa (Fáza 2 učiteľského kanála).

    Učiteľ (PLUS) založí triedu, žiaci sa pridávajú kódom `join_code`.
    Sady priradené triede (ClassCategory) vidia členovia live — bez kópie.
    """
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    join_code = Column(String(16), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # cascade: pri zmazaní učiteľa ORM zmaže aj jeho triedy (inak by nulovalo NOT NULL FK)
    teacher = relationship("User", backref=backref("teaching_classes", cascade="all, delete-orphan"))
    members = relationship("ClassMember", back_populates="school_class", cascade="all, delete-orphan")
    categories = relationship("ClassCategory", back_populates="school_class", cascade="all, delete-orphan")


class ClassMember(Base):
    """Členstvo žiaka v triede. `nickname` je identita v rámci triedy
    (login pseudonymných účtov = kód triedy + prezývka + heslo)."""
    __tablename__ = "class_members"
    __table_args__ = (
        UniqueConstraint("class_id", "user_id", name="uq_class_members_class_user"),
        UniqueConstraint("class_id", "nickname", name="uq_class_members_class_nickname"),
    )

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    nickname = Column(String(50), nullable=False)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    school_class = relationship("SchoolClass", back_populates="members")
    user = relationship("User", backref=backref("class_memberships", cascade="all, delete-orphan"))


class ClassCategory(Base):
    """Priradenie učiteľovej kategórie triede (live odkaz, nie kópia)."""
    __tablename__ = "class_categories"
    __table_args__ = (
        UniqueConstraint("class_id", "category_id", name="uq_class_categories_class_category"),
    )

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())

    school_class = relationship("SchoolClass", back_populates="categories")
    category = relationship("Category")
