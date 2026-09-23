from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field

from app.schemas.api_key import ApiKeyBase


class ApiKey(ApiKeyBase, table=True):
    __tablename__ = "api_keys"

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", ondelete="CASCADE")
    key_hash: str = Field(index=True, unique=True, max_length=64)
    created_by: int = Field(foreign_key="users.id", ondelete="CASCADE")
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    last_used_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
