"""add api_id to api_keys

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2025-04-17 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column(
            "api_id",
            sa.UUID(),
            sa.ForeignKey("external_apis.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_api_keys_api_id", "api_keys", ["api_id"])


def downgrade() -> None:
    op.drop_index("ix_api_keys_api_id", table_name="api_keys")
    op.drop_column("api_keys", "api_id")
