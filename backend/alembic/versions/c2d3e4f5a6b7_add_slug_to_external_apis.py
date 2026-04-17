"""add slug to external_apis

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-04-17 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "external_apis",
        sa.Column("slug", sa.String(200), nullable=True),
    )
    op.create_index(
        op.f("ix_external_apis_slug"), "external_apis", ["slug"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_external_apis_slug"), table_name="external_apis")
    op.drop_column("external_apis", "slug")
