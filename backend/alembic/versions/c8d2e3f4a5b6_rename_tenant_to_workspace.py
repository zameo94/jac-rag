"""rename tenant to workspace

Revision ID: c8d2e3f4a5b6
Revises: b7c1d2e3f4a5
Create Date: 2026-09-23 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c8d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'b7c1d2e3f4a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

WORKSPACE_ID_TABLES = ("memberships", "api_keys", "documents", "conversations", "invitations")

INDEX_RENAMES = (
    ("ix_tenants_slug", "ix_workspaces_slug"),
    ("ix_documents_tenant_id", "ix_documents_workspace_id"),
    ("ix_conversations_tenant_end_user", "ix_conversations_workspace_end_user"),
    ("ix_conversations_tenant_user", "ix_conversations_workspace_user"),
)

CONSTRAINT_RENAMES = (
    ("memberships", "uq_memberships_user_tenant", "uq_memberships_user_workspace"),
)

SETTINGS_SCOPE_OLD = sa.Enum("tenant", "user", name="settingscope", native_enum=False)
SETTINGS_SCOPE_NEW = sa.Enum(
    "workspace", "user", "global", name="settingscope", native_enum=False
)


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table("tenants", "workspaces")
    for table in WORKSPACE_ID_TABLES:
        op.alter_column(table, "tenant_id", new_column_name="workspace_id")

    op.alter_column(
        "settings",
        "scope_type",
        type_=SETTINGS_SCOPE_NEW,
        existing_type=SETTINGS_SCOPE_OLD,
    )
    op.execute("UPDATE settings SET scope_type = 'workspace' WHERE scope_type = 'tenant'")

    if op.get_bind().dialect.name == "postgresql":
        for old, new in INDEX_RENAMES:
            op.execute(f"ALTER INDEX {old} RENAME TO {new}")
        for table, old, new in CONSTRAINT_RENAMES:
            op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {old} TO {new}")


def downgrade() -> None:
    """Downgrade schema."""
    if op.get_bind().dialect.name == "postgresql":
        for table, old, new in CONSTRAINT_RENAMES:
            op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {new} TO {old}")
        for old, new in INDEX_RENAMES:
            op.execute(f"ALTER INDEX {new} RENAME TO {old}")

    op.execute("UPDATE settings SET scope_type = 'tenant' WHERE scope_type = 'workspace'")
    op.alter_column(
        "settings",
        "scope_type",
        type_=SETTINGS_SCOPE_OLD,
        existing_type=SETTINGS_SCOPE_NEW,
    )

    for table in WORKSPACE_ID_TABLES:
        op.alter_column(table, "workspace_id", new_column_name="tenant_id")
    op.rename_table("workspaces", "tenants")
