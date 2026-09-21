from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Column
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ConversationBase(SQLModel):
    title: Optional[str] = Field(default=None, max_length=200)


class ConversationRead(ConversationBase):
    id: int
    tenant_id: int
    user_id: Optional[int] = None
    end_user_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MessageBase(SQLModel):
    role: MessageRole = Field(
        sa_column=Column(
            SAEnum(MessageRole, native_enum=False),
            nullable=False,
        )
    )
    content: str
    provider: Optional[str] = Field(default=None, max_length=32)
    model: Optional[str] = Field(default=None, max_length=120)
    grounded: Optional[bool] = None
    error_code: Optional[str] = Field(default=None, max_length=48)
    sources: Optional[list[dict]] = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )


class MessageRead(MessageBase):
    id: int
    conversation_id: int
    created_at: datetime


class ConversationDetail(ConversationRead):
    messages: list[MessageRead] = []
