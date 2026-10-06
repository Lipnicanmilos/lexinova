from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
from typing import List, Optional
import enum

from app.models.word import clean_example

class KnowledgeLevel(str, enum.Enum):
    DONT_KNOW = "dont_know"
    LEARNING = "learning"
    KNOW = "know"

class WordBase(BaseModel):
    original_word: str
    translation: str
    category_id: int
    language_from: Optional[str] = "en"
    language_to: Optional[str] = "sk"
    # Príkladová veta je vždy v jazyku slova — pri opačnom smere testu sa
    # na rozdiel od original_word/translation neprehadzuje.
    example_sentence: Optional[str] = None
    example_translation: Optional[str] = None

    @field_validator("example_sentence", "example_translation", mode="before")
    @classmethod
    def _clean_example(cls, value):
        return clean_example(value)

class WordCreate(WordBase):
    pass

class WordUpdate(BaseModel):
    original_word: Optional[str] = None
    translation: Optional[str] = None
    category_id: Optional[int] = None
    knowledge_level: Optional[KnowledgeLevel] = None
    # Prázdny reťazec vetu zmaže (clean_example z neho spraví None).
    example_sentence: Optional[str] = None
    example_translation: Optional[str] = None

    @field_validator("example_sentence", "example_translation", mode="before")
    @classmethod
    def _clean_example(cls, value):
        return clean_example(value)

class WordResponse(WordBase):
    id: int
    user_id: Optional[int] = None
    knowledge_level: KnowledgeLevel
    times_tested: int
    times_correct: int
    last_tested: Optional[datetime] = None
    success_rate: float
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class WordListResponse(BaseModel):
    words: List[WordResponse]
    total: int

class TestConfig(BaseModel):
    category_id: Optional[int] = None
    knowledge_levels: List[KnowledgeLevel]
    limit: int = Field(default=10, ge=1, le=1000)  # Limit between 1 and 1000
    test_direction: str = "original_to_translation"  # "original_to_translation" or "translation_to_original"

class ClozeItem(BaseModel):
    """Jedna úloha dopĺňania do vety. `id`, `original_word` a `translation`
    sú z toho istého slova — výsledok sa odosiela rovnako ako pri kartičkách."""
    id: int
    original_word: str
    translation: str
    language_from: Optional[str] = "en"
    sentence_before: str
    # Tvar, ktorý vo vete naozaj stojí (heslo „travel", vo vete „travelled").
    sentence_hidden: str
    sentence_after: str
    sentence_translation: Optional[str] = None
    options: List[str]
    # Správna možnosť: heslo, alebo pri fráze jej vynechané slovo.
    answer: str

class TestResult(BaseModel):
    word_id: int
    is_correct: bool

class ReviewSession(BaseModel):
    """Dokoncene prehravanie v Opakovani (auto-play) — pocet prejdenych kariet."""
    category_id: Optional[int] = None
    words_reviewed: int = Field(ge=1, le=10000)


class KnowledgeLevelUpdate(BaseModel):
    knowledge_level: KnowledgeLevel
