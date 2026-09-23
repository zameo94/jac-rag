from enum import Enum
from typing import Optional

from pydantic import field_validator
from sqlalchemy import Column
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class DocumentBase(SQLModel):
    filename: str = Field(min_length=1, max_length=255)
    mime: str = Field(max_length=100)
    size: int = Field(ge=0)
    language: Optional[str] = Field(default=None, max_length=8)
    status: DocumentStatus = Field(
        default=DocumentStatus.PENDING,
        sa_column=Column(SAEnum(DocumentStatus, native_enum=False), nullable=False),
    )
    error: Optional[str] = Field(default=None, max_length=500)
    chunk_count: Optional[int] = Field(default=None, ge=0)

    @field_validator("filename", mode="before")
    @classmethod
    def normalize_filename(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class DocumentRead(DocumentBase):
    id: int
    workspace_id: int
    uploader_id: int


class DocumentStatusRead(SQLModel):
    id: int
    status: DocumentStatus
    error: Optional[str] = None
    chunk_count: Optional[int] = None
