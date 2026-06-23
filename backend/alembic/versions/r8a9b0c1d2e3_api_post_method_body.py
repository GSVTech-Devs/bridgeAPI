"""API POST: request_method + request_body_template em external_apis

Revision ID: r8a9b0c1d2e3
Revises: q7f8a9b0c1d2
Create Date: 2026-06-23 05:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "r8a9b0c1d2e3"
down_revision = "q7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "external_apis",
        sa.Column("request_method", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "external_apis",
        sa.Column("request_body_template", sa.String(length=8192), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("external_apis", "request_body_template")
    op.drop_column("external_apis", "request_method")
