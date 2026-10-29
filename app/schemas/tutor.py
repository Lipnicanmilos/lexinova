from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.services.tutor_service import TUTOR_LANGUAGES, TUTOR_LEVELS, TUTOR_MESSAGE_MAX_LENGTH


class TutorStartRequest(BaseModel):
    # Prázdne = ponechať, čo je v profile (alebo odhad AI z minulej relácie).
    level: Optional[str] = None
    language_from: Optional[str] = None
    # Relácia nad vlastnou sadou: tútor do rozhovoru zapája jej slovíčka.
    category_id: Optional[int] = None

    @field_validator("level")
    @classmethod
    def _known_level(cls, value):
        if value is not None and value not in TUTOR_LEVELS:
            raise ValueError(f"level must be one of {', '.join(TUTOR_LEVELS)}")
        return value

    @field_validator("language_from")
    @classmethod
    def _known_language(cls, value):
        if value is not None and value not in TUTOR_LANGUAGES:
            raise ValueError(f"language_from must be one of {', '.join(TUTOR_LANGUAGES)}")
        return value


class TutorStartResponse(BaseModel):
    session_id: int
    reply: str
    level: str
    language_from: str
    messages_left: int
    messages_left_today: int
    # {category_id, name, words: [{word, translation}]} pri relácii nad sadou
    focus: Optional[dict] = None


class TutorMessageRequest(BaseModel):
    # Presnú hranicu stráži endpoint (po orezaní medzier); tu len hrubá poistka.
    text: str = Field(min_length=1, max_length=TUTOR_MESSAGE_MAX_LENGTH * 2)


class TutorMessageResponse(BaseModel):
    reply: str
    correction: Optional[str] = None
    # Pomoc v materinskom jazyku („ⓘ …"), keď používateľ hovoril po slovensky
    help: Optional[str] = None
    messages_left: int
    messages_left_today: int


class TutorEndResponse(BaseModel):
    summary: Optional[str] = None
    words_added: int = 0
    level: Optional[str] = None
    already_ended: bool = False
