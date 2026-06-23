"""proxies por API (sem pools) + flags uses_proxy / proxy_managed_by_client

Remove a camada de pool da 4a (proxy_pools, api_client_proxy_pool,
external_apis.proxy_pool_id) e re-ancora `proxies` em `api_id`. Cada API decide
se usa proxy (`uses_proxy`); cada permissão decide se o cliente gerencia o
próprio proxy (`proxy_managed_by_client`).

Revision ID: p6e7f8a9b0c1
Revises: o5d6e7f8a9b0
Create Date: 2026-06-23 03:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p6e7f8a9b0c1"
down_revision = "o5d6e7f8a9b0"
branch_labels = None
depends_on = None


def _create_proxies_per_api() -> None:
    op.create_table(
        "proxies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("api_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["api_id"], ["external_apis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_proxies_api_id", "proxies", ["api_id"])
    op.create_index("ix_proxies_account_id", "proxies", ["account_id"])
    op.create_index("ix_proxies_status", "proxies", ["status"])


def upgrade() -> None:
    op.add_column(
        "external_apis",
        sa.Column(
            "uses_proxy",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "permissions",
        sa.Column(
            "proxy_managed_by_client",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # remover a camada de pool da 4a
    op.drop_constraint(
        "fk_external_apis_proxy_pool_id", "external_apis", type_="foreignkey"
    )
    op.drop_index("ix_external_apis_proxy_pool_id", table_name="external_apis")
    op.drop_column("external_apis", "proxy_pool_id")

    op.drop_table("api_client_proxy_pool")  # dropa índices/constraints junto
    op.drop_table("proxies")  # versão pool-based
    op.drop_table("proxy_pools")

    _create_proxies_per_api()


def downgrade() -> None:
    op.drop_table("proxies")  # versão por-API

    # recriar proxy_pools (estado o5d6e7f8a9b0)
    op.create_table(
        "proxy_pools",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_proxy_pools_account_id", "proxy_pools", ["account_id"])
    op.create_index("ix_proxy_pools_name", "proxy_pools", ["name"])
    op.create_unique_constraint(
        "uq_proxy_pools_account_name", "proxy_pools", ["account_id", "name"]
    )
    op.create_foreign_key(
        "fk_proxy_pools_account_id",
        "proxy_pools",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # recriar proxies pool-based
    op.create_table(
        "proxies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["pool_id"], ["proxy_pools.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_proxies_account_id", "proxies", ["account_id"])
    op.create_index("ix_proxies_pool_id", "proxies", ["pool_id"])
    op.create_index("ix_proxies_status", "proxies", ["status"])

    # recriar api_client_proxy_pool
    op.create_table(
        "api_client_proxy_pool",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("api_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("pool_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["api_id"], ["external_apis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pool_id"], ["proxy_pools.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("api_id", "account_id", name="uq_api_client_proxy_pool"),
    )
    op.create_index(
        "ix_api_client_proxy_pool_api_id", "api_client_proxy_pool", ["api_id"]
    )
    op.create_index(
        "ix_api_client_proxy_pool_account_id", "api_client_proxy_pool", ["account_id"]
    )

    # external_apis.proxy_pool_id
    op.add_column(
        "external_apis", sa.Column("proxy_pool_id", sa.Uuid(), nullable=True)
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

    op.drop_column("permissions", "proxy_managed_by_client")
    op.drop_column("external_apis", "uses_proxy")
