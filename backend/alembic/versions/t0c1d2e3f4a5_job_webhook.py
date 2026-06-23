"""proxy_jobs: callback_url + webhook_status (entrega assíncrona — 5b)

Revision ID: t0c1d2e3f4a5
Revises: s9b0c1d2e3f4
Create Date: 2026-06-23 07:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "t0c1d2e3f4a5"
down_revision = "s9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("proxy_jobs", sa.Column("callback_url", sa.String(length=2048), nullable=True))
    op.add_column("proxy_jobs", sa.Column("webhook_status", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("proxy_jobs", "webhook_status")
    op.drop_column("proxy_jobs", "callback_url")
