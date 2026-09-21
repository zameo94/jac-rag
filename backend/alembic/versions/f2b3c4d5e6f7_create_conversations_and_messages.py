"""create conversations and messages

Revision ID: f2b3c4d5e6f7
Revises: e1a2b3c4d5e6
Create Date: 2026-09-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'f2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = 'e1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('conversations',
    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('end_user_id', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('(user_id IS NULL) <> (end_user_id IS NULL)', name='ck_conversations_single_actor'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_conversations_tenant_end_user', 'conversations', ['tenant_id', 'end_user_id', 'updated_at'], unique=False)
    op.create_index('ix_conversations_tenant_user', 'conversations', ['tenant_id', 'user_id', 'updated_at'], unique=False)

    op.create_table('messages',
    sa.Column('role', sa.Enum('user', 'assistant', name='messagerole', native_enum=False), nullable=False),
    sa.Column('content', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('provider', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True),
    sa.Column('model', sqlmodel.sql.sqltypes.AutoString(length=120), nullable=True),
    sa.Column('grounded', sa.Boolean(), nullable=True),
    sa.Column('error_code', sqlmodel.sql.sqltypes.AutoString(length=48), nullable=True),
    sa.Column('sources', sa.JSON(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('conversation_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_messages_conversation_id'), 'messages', ['conversation_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_messages_conversation_id'), table_name='messages')
    op.drop_table('messages')
    op.drop_index('ix_conversations_tenant_user', table_name='conversations')
    op.drop_index('ix_conversations_tenant_end_user', table_name='conversations')
    op.drop_table('conversations')
