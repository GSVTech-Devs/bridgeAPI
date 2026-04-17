"""add url_template to external_apis

Revision ID: b1c2d3e4f5a6
Revises: a3f1c8e92b45
Create Date: 2026-04-17 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "b1c2d3e4f5a6"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "external_apis",
        sa.Column("url_template", sa.String(4096), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("external_apis", "url_template")
