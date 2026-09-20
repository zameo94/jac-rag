from enum import Enum
from typing import Any, Optional

from pydantic import field_validator
from sqlalchemy import JSON, Column
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel


class SettingScope(str, Enum):
    GLOBAL = "global"
    TENANT = "tenant"
    USER = "user"


def _scope_values(enum_class) -> list[str]:
    return [member.value for member in enum_class]


class SettingBase(SQLModel):
    scope_type: SettingScope = Field(
        sa_column=Column(
            SAEnum(SettingScope, native_enum=False, values_callable=_scope_values),
            nullable=False,
        ),
    )
    scope_id: Optional[int] = Field(default=None)
    type: str = Field(min_length=1, max_length=50)
    key: str = Field(min_length=1, max_length=100)
    value: Any = Field(sa_column=Column(JSON, nullable=False))

    @field_validator("scope_id")
    @classmethod
    def validate_scope_id(cls, value, info):
        scope_type = info.data.get("scope_type")
        if scope_type is SettingScope.GLOBAL:
            if value is not None:
                raise ValueError("Global settings must have scope_id = null")
            return None
        if value is None or value < 1:
            raise ValueError("Tenant and user settings require scope_id >= 1")
        return value

    @field_validator("type", "key", mode="before")
    @classmethod
    def normalize_token(cls, value):
        if isinstance(value, str):
            return value.strip().lower()
        return value


class SettingRead(SettingBase):
    id: int
