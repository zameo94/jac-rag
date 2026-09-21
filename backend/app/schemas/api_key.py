from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class ApiKeyBase(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    prefix: str = Field(max_length=16)
    is_active: bool = Field(default=True)


class ApiKeyCreate(SQLModel):
    name: str = Field(min_length=1, max_length=100)


class ApiKeyUpdate(SQLModel):
    is_active: bool


class ApiKeyRead(ApiKeyBase):
    id: int
    tenant_id: int
    created_at: datetime
    last_used_at: Optional[datetime] = None


class ApiKeyCreated(ApiKeyRead):
    key: str
