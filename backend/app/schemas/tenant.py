import re
from enum import Enum
from typing import Optional

from pydantic import field_validator
from sqlalchemy import Column
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from app.schemas.user import normalize_locale_value


class AnswerMode(str, Enum):
    STRICT = "strict"
    ASSISTIVE = "assistive"


def slugify_value(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    return normalized.strip("-")


class TenantBase(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(index=True, unique=True, min_length=1, max_length=60)
    default_locale: str = Field(default="it", max_length=8)
    answer_mode: AnswerMode = Field(
        default=AnswerMode.STRICT,
        sa_column=Column(
            SAEnum(AnswerMode, native_enum=False),
            nullable=False,
            server_default=AnswerMode.STRICT.value,
        ),
    )

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("slug", mode="before")
    @classmethod
    def normalize_slug(cls, value):
        if not isinstance(value, str):
            return value
        normalized = slugify_value(value)
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized):
            raise ValueError("Slug must contain lowercase letters, numbers and hyphens")
        return normalized

    @field_validator("default_locale", mode="before")
    @classmethod
    def normalize_default_locale(cls, value):
        return normalize_locale_value(value)


class TenantCreate(TenantBase):
    slug: Optional[str] = Field(default=None, max_length=60)


class TenantRead(TenantBase):
    id: int
