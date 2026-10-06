from typing import List, Literal

from pydantic import BaseModel, Field, field_validator

from app.services.ai_chat_service import (
    CHAT_DEFAULT_LEVEL,
    CHAT_LEVELS,
    CHAT_MAX_USER_MESSAGES,
    CHAT_REPLY_MAX_LENGTH,
)


class ChatStartRequest(BaseModel):
    level: str = CHAT_DEFAULT_LEVEL

    @field_validator("level")
    @classmethod
    def _known_level(cls, value: str) -> str:
        if value not in CHAT_LEVELS:
            raise ValueError(f"level must be one of {', '.join(CHAT_LEVELS)}")
        return value


class ChatWord(BaseModel):
    original_word: str
    translation: str


class ChatStartResponse(BaseModel):
    # Podpísaný lístok rozhovoru: komu patrí, ktorá sada, ktoré slová a úroveň.
    # Klient ho len vracia späť — server podľa neho zloží pokyny pre AI.
    token: str
    words: List[ChatWord]
    reply: str
    messages_left: int


class ChatMessage(BaseModel):
    role: Literal["assistant", "user"]
    # Horná hranica je dĺžka odpovede AI; kratší limit pre správy používateľa
    # stráži endpoint (potrebuje vedieť, čia správa to je).
    text: str = Field(min_length=1, max_length=CHAT_REPLY_MAX_LENGTH)


class ChatReplyRequest(BaseModel):
    token: str = Field(min_length=1, max_length=2000)
    # Celá doterajšia história: začína správou AI, končí správou používateľa.
    messages: List[ChatMessage] = Field(min_length=2, max_length=2 * CHAT_MAX_USER_MESSAGES)


class ChatReplyResponse(BaseModel):
    reply: str
    messages_left: int
