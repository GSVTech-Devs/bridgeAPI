"""create proxies and proxy_pools tables

Revision ID: n4c5d6e7f8a9
Revises: m3b4c5d6e7f8
Create Date: 2026-06-23 01:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "n4c5d6e7f8a9"
down_revision = "m3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proxy_pools",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_proxy_pools_name", "proxy_pools", ["name"], unique=True)

    op.create_table(
        "proxies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("pool_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=255), nullable=True),
        sa.Column("ownership", sa.String(length=20), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("scheme", sa.String(length=10), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("username_encrypted", sa.String(length=2048), nullable=True),
        sa.Column("password_encrypted", sa.String(length=2048), nullable=True),
        sa.Column("rotation", sa.String(length=20), nullable=False),
        sa.Column("session_ttl_s", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(length=1024), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["pool_id"], ["proxy_pools.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_proxies_pool_id", "proxies", ["pool_id"])
    op.create_index("ix_proxies_status", "proxies", ["status"])

    op.add_column(
        "external_apis",
        sa.Column("proxy_pool_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_external_apis_proxy_pool_id", "external_apis", ["proxy_pool_id"]
    )
    op.create_foreign_key(
        "fk_external_apis_proxy_pool_id",
        "external_apis",
        "proxy_pools",
        ["proxy_pool_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_external_apis_proxy_pool_id", "external_apis", type_="foreignkey"
    )
    op.drop_index("ix_external_apis_proxy_pool_id", table_name="external_apis")
    op.drop_column("external_apis", "proxy_pool_id")

    op.drop_index("ix_proxies_status", table_name="proxies")
    op.drop_index("ix_proxies_pool_id", table_name="proxies")
    op.drop_table("proxies")

    op.drop_index("ix_proxy_pools_name", table_name="proxy_pools")
    op.drop_table("proxy_pools")
