from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, Column, DateTime, Index, func
from sqlmodel import Field, Relationship

from app.schemas.conversation import ConversationBase

if TYPE_CHECKING:
    from app.models.message import Message


class Conversation(ConversationBase, table=True):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(
            "(user_id IS NULL) <> (end_user_id IS NULL)",
            name="ck_conversations_single_actor",
        ),
        Index(
            "ix_conversations_workspace_end_user",
            "workspace_id",
            "end_user_id",
            "updated_at",
        ),
        Index(
            "ix_conversations_workspace_user",
            "workspace_id",
            "user_id",
            "updated_at",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspaces.id", ondelete="CASCADE")
    user_id: Optional[int] = Field(
        default=None, foreign_key="users.id", ondelete="CASCADE"
    )
    end_user_id: Optional[str] = Field(default=None, max_length=64)
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

    messages: list["Message"] = Relationship(
        back_populates="conversation", passive_deletes=True
    )
