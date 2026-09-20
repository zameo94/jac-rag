"""create settings

Revision ID: a5b8c2d4e6f0
Revises: 738bfb90ec93
Create Date: 2026-09-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'a5b8c2d4e6f0'
down_revision: Union[str, Sequence[str], None] = '738bfb90ec93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('settings',
    sa.Column('scope_type', sa.Enum('tenant', 'user', name='settingscope', native_enum=False), nullable=False),
    sa.Column('scope_id', sa.Integer(), nullable=False),
    sa.Column('type', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
    sa.Column('key', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
    sa.Column('value', sa.JSON(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('scope_type', 'scope_id', 'type', 'key', name='uq_settings_scope')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('settings')
