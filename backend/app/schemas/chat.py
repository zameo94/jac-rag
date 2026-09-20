from typing import Optional

from sqlmodel import Field, SQLModel


class ChatRequest(SQLModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[int] = Field(default=None, ge=1)


class ChatSource(SQLModel):
    document_id: int
    filename: str
    chunk_index: int
    score: float


class ChatResponse(SQLModel):
    answer: str
    provider: str
    model: str
    grounded: bool
    sources: list[ChatSource]
