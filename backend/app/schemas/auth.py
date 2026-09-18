from pydantic import EmailStr, field_validator
from sqlmodel import Field, SQLModel

from app.schemas.user import normalize_email_value, normalize_locale_value


class RegisterRequest(SQLModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    locale: str = Field(default="it", max_length=8)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return normalize_email_value(value)

    @field_validator("locale", mode="before")
    @classmethod
    def normalize_locale(cls, value):
        return normalize_locale_value(value)


class LoginRequest(SQLModel):
    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return normalize_email_value(value)
