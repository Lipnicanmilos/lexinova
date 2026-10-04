from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

from app.models.word import clean_example


class AICategoryWord(BaseModel):
    original_word: str
    translation: str
    language_from: str = "en"
    language_to: str = "sk"
    # Nepovinné: pri väčších sadách sa vety negenerujú (viď EXAMPLES_INLINE_MAX_COUNT)
    # a fotka či video ich nevracajú vôbec.
    example_sentence: Optional[str] = None
    example_translation: Optional[str] = None

    @field_validator("example_sentence", "example_translation", mode="before")
    @classmethod
    def _clean_example(cls, value):
        return clean_example(value)


class AICategoryCreateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    language_from: str = "en"
    language_to: str = "sk"
    count: int = Field(default=25, ge=5, le=200)
    ai_provider: str = Field(default="gemini")


class AICategoryFromVideoRequest(BaseModel):
    video_url: str = Field(min_length=8, max_length=500)
    language_from: str = "en"
    language_to: str = "sk"


class AICategoryCreateResponse(BaseModel):
    category_id: int
    category_name: str
    category_description: Optional[str] = None
    inserted_words: int
    skipped_words: int
    words: List[AICategoryWord]


class AICategoryPreviewResponse(BaseModel):
    """Návrh na odsúhlasenie — nič z toho zatiaľ nie je v databáze."""
    category_name: str
    category_description: Optional[str] = None
    words: List[AICategoryWord]


class AICategorySaveRequest(BaseModel):
    """To, čo používateľ v náhľade nechal (odškrtané slová sem už neprídu)."""
    category_name: str = Field(min_length=1, max_length=100)
    category_description: Optional[str] = Field(default=None, max_length=500)
    language_from: str = "en"
    language_to: str = "sk"
    words: List[AICategoryWord] = Field(min_length=1, max_length=200)
