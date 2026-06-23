"""add service_token to external_apis

Revision ID: m3b4c5d6e7f8
Revises: l2a3b4c5d6e7
Create Date: 2026-06-23 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "m3b4c5d6e7f8"
down_revision = "l2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "external_apis",
        sa.Column("service_token_prefix", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "external_apis",
        sa.Column("service_token_hash", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_external_apis_service_token_prefix",
        "external_apis",
        ["service_token_prefix"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_external_apis_service_token_prefix", table_name="external_apis"
    )
    op.drop_column("external_apis", "service_token_hash")
    op.drop_column("external_apis", "service_token_prefix")
