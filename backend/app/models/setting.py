from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Index, func, text
from sqlmodel import Field, UniqueConstraint

from app.schemas.setting import SettingBase


class Setting(SettingBase, table=True):
    __tablename__ = "settings"
    __table_args__ = (
        UniqueConstraint(
            "scope_type", "scope_id", "type", "key", name="uq_settings_scope"
        ),
        Index(
            "uq_settings_global",
            "type",
            "key",
            unique=True,
            sqlite_where=text("scope_id IS NULL"),
            postgresql_where=text("scope_id IS NULL"),
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )
