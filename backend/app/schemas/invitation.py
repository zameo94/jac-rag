from datetime import datetime

from pydantic import EmailStr, field_validator
from sqlalchemy import Column
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from app.schemas.membership import MembershipRole, validate_assignable_role
from app.schemas.user import normalize_email_value


class InvitationBase(SQLModel):
    email: EmailStr = Field(index=True)
    role: MembershipRole = Field(
        sa_column=Column(SAEnum(MembershipRole, native_enum=False), nullable=False),
    )
    expires_at: datetime

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return normalize_email_value(value)


class InvitationCreate(SQLModel):
    email: EmailStr
    role: MembershipRole = MembershipRole.MEMBER

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return normalize_email_value(value)

    @field_validator("role")
    @classmethod
    def role_must_be_assignable(cls, value):
        return validate_assignable_role(value)


class InvitationCreated(SQLModel):
    id: int
    workspace_id: int
    email: EmailStr
    role: MembershipRole
    token: str
    expires_at: datetime
