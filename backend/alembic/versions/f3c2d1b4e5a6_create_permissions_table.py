"""create permissions table

Revision ID: f3c2d1b4e5a6
Revises: eb4ad1d0d2e9
Create Date: 2026-04-02 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "f3c2d1b4e5a6"
down_revision: Union[str, Sequence[str], None] = "eb4ad1d0d2e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "permissions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("api_id", sa.UUID(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["api_id"], ["external_apis.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", "api_id", name="uq_permission_client_api"),
    )
    op.create_index("ix_permissions_client_id", "permissions", ["client_id"])
    op.create_index("ix_permissions_api_id", "permissions", ["api_id"])


def downgrade() -> None:
    op.drop_index("ix_permissions_api_id", table_name="permissions")
    op.drop_index("ix_permissions_client_id", table_name="permissions")
    op.drop_table("permissions")
