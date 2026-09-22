from typing import Optional

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.schemas.user import normalize_locale_value


class ChatRequest(SQLModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[int] = Field(default=None, ge=1)
    locale: Optional[str] = None

    @field_validator("locale", mode="before")
    @classmethod
    def normalize_locale(cls, value):
        return normalize_locale_value(value)


class ChatSource(SQLModel):
    document_id: int
    filename: str
    chunk_index: int
    score: float


class ChatResponse(SQLModel):
    conversation_id: int
    answer: str
    provider: str
    model: str
    grounded: bool
    sources: list[ChatSource]
