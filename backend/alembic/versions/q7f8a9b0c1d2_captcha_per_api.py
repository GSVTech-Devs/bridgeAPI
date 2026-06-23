"""captcha por API (provedores) + flags uses_captcha / captcha_managed_by_client

Espelha a 4a (proxy por API): cada API tem seus provedores de captcha (admin
e/ou cliente), com saldo e monitoramento.

Revision ID: q7f8a9b0c1d2
Revises: p6e7f8a9b0c1
Create Date: 2026-06-23 04:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "q7f8a9b0c1d2"
down_revision = "p6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "external_apis",
        sa.Column(
            "uses_captcha",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "permissions",
        sa.Column(
            "captcha_managed_by_client",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.create_table(
        "captcha_providers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("api_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=255), nullable=True),
        sa.Column("api_key_encrypted", sa.String(length=2048), nullable=True),
        sa.Column("balance_usd", sa.Float(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("last_error", sa.String(length=1024), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["api_id"], ["external_apis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_captcha_providers_api_id", "captcha_providers", ["api_id"])
    op.create_index(
        "ix_captcha_providers_account_id", "captcha_providers", ["account_id"]
    )
    op.create_index("ix_captcha_providers_status", "captcha_providers", ["status"])


def downgrade() -> None:
    op.drop_table("captcha_providers")
    op.drop_column("permissions", "captcha_managed_by_client")
    op.drop_column("external_apis", "uses_captcha")
