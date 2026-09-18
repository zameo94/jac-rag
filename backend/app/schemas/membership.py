from datetime import datetime
from enum import Enum

from pydantic import EmailStr, field_validator
from sqlalchemy import Column
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel


class MembershipRole(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


def validate_assignable_role(value: MembershipRole) -> MembershipRole:
    if value is MembershipRole.OWNER:
        raise ValueError("The OWNER role cannot be assigned")
    return value


class MembershipBase(SQLModel):
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE")
    tenant_id: int = Field(foreign_key="tenants.id", ondelete="CASCADE")
    role: MembershipRole = Field(
        sa_column=Column(SAEnum(MembershipRole, native_enum=False), nullable=False),
    )


class MembershipCreate(MembershipBase):
    pass


class MembershipRead(MembershipBase):
    id: int


class MemberRead(SQLModel):
    id: int
    user_id: int
    tenant_id: int
    role: MembershipRole
    email: EmailStr
    created_at: datetime


class MemberUpdate(SQLModel):
    role: MembershipRole

    @field_validator("role")
    @classmethod
    def role_must_be_assignable(cls, value):
        return validate_assignable_role(value)
