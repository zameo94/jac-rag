from typing import Optional

from pydantic import EmailStr, field_validator
from sqlmodel import Field, SQLModel

SUPPORTED_LOCALES = {"it", "en"}


def normalize_email_value(value):
    if isinstance(value, str):
        return value.strip().lower()
    return value


def normalize_locale_value(value):
    if value is None:
        return value
    if not isinstance(value, str) or value.strip().lower() not in SUPPORTED_LOCALES:
        raise ValueError(f"Unsupported locale: {value}")
    return value.strip().lower()


class UserBase(SQLModel):
    email: EmailStr = Field(index=True, unique=True)
    locale: str = Field(default="it", max_length=8)
    is_active: bool = Field(default=True)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return normalize_email_value(value)

    @field_validator("locale", mode="before")
    @classmethod
    def normalize_locale(cls, value):
        return normalize_locale_value(value)


class UserCreate(UserBase):
    pass


class UserUpdate(UserBase):
    email: Optional[EmailStr] = None
    locale: Optional[str] = None
    is_active: Optional[bool] = None


class UserRead(UserBase):
    id: int
