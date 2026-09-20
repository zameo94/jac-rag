"""add global settings scope

Revision ID: d6f1a2b3c4d5
Revises: a5b8c2d4e6f0
Create Date: 2026-09-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6f1a2b3c4d5'
down_revision: Union[str, Sequence[str], None] = 'a5b8c2d4e6f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('settings') as batch_op:
        batch_op.alter_column('scope_id', existing_type=sa.Integer(), nullable=True)
    op.create_index(
        'uq_settings_global',
        'settings',
        ['type', 'key'],
        unique=True,
        postgresql_where=sa.text('scope_id IS NULL'),
        sqlite_where=sa.text('scope_id IS NULL'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_settings_global', table_name='settings')
    with op.batch_alter_table('settings') as batch_op:
        batch_op.alter_column('scope_id', existing_type=sa.Integer(), nullable=False)
