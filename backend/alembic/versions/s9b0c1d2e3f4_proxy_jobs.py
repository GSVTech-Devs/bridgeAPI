"""proxy_jobs: execução híbrida (jobs assíncronos) — Fase 5

Revision ID: s9b0c1d2e3f4
Revises: r8a9b0c1d2e3
Create Date: 2026-06-23 06:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "s9b0c1d2e3f4"
down_revision = "r8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proxy_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("api_id", sa.Uuid(), nullable=False),
        sa.Column("key_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("request_snapshot", sa.JSON(), nullable=True),
        sa.Column("result_body", sa.Text(), nullable=True),
        sa.Column("result_status_code", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("cost", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["api_id"], ["external_apis.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("account_id", "idempotency_key", name="uq_proxy_jobs_idem"),
    )
    op.create_index("ix_proxy_jobs_correlation_id", "proxy_jobs", ["correlation_id"])
    op.create_index("ix_proxy_jobs_account_id", "proxy_jobs", ["account_id"])
    op.create_index("ix_proxy_jobs_api_id", "proxy_jobs", ["api_id"])
    op.create_index("ix_proxy_jobs_status", "proxy_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("proxy_jobs")
