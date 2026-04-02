"""create external_apis and endpoints tables

Revision ID: a3f1c8e92b45
Revises: 76f693953ed4
Create Date: 2026-04-02 12:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f1c8e92b45"
down_revision: Union[str, Sequence[str], None] = "76f693953ed4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "external_apis",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("base_url", sa.String(2048), nullable=False),
        sa.Column("master_key_encrypted", sa.String(2048), nullable=True),
        sa.Column(
            "auth_type",
            sa.String(20),
            nullable=False,
            server_default="none",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_external_apis_name", "external_apis", ["name"], unique=True)
    op.create_index(
        "ix_external_apis_status", "external_apis", ["status"], unique=False
    )

    op.create_table(
        "endpoints",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("api_id", sa.UUID(), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("path", sa.String(1024), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
        ),
        sa.Column("cost_rule", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["api_id"], ["external_apis.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_endpoints_api_id", "endpoints", ["api_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_endpoints_api_id", table_name="endpoints")
    op.drop_table("endpoints")
    op.drop_index("ix_external_apis_status", table_name="external_apis")
    op.drop_index("ix_external_apis_name", table_name="external_apis")
    op.drop_table("external_apis")
