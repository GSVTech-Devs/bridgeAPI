"""account scoping for proxies + per-client pool override

Revision ID: o5d6e7f8a9b0
Revises: n4c5d6e7f8a9
Create Date: 2026-06-23 02:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "o5d6e7f8a9b0"
down_revision = "n4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- proxy_pools: dono (account_id) + unicidade de nome por dono ---------
    op.add_column(
        "proxy_pools",
        sa.Column("account_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_proxy_pools_account_id", "proxy_pools", ["account_id"]
    )
    op.create_foreign_key(
        "fk_proxy_pools_account_id",
        "proxy_pools",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="CASCADE",
    )
    # nome era único globalmente; passa a ser único por dono (account_id, name).
    op.drop_index("ix_proxy_pools_name", table_name="proxy_pools")
    op.create_index("ix_proxy_pools_name", "proxy_pools", ["name"])
    op.create_unique_constraint(
        "uq_proxy_pools_account_name", "proxy_pools", ["account_id", "name"]
    )

    # --- proxies: dono (account_id) -----------------------------------------
    op.add_column(
        "proxies",
        sa.Column("account_id", sa.Uuid(), nullable=True),
    )
    op.create_index("ix_proxies_account_id", "proxies", ["account_id"])
    op.create_foreign_key(
        "fk_proxies_account_id",
        "proxies",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # --- override por cliente: api_client_proxy_pool ------------------------
    op.create_table(
        "api_client_proxy_pool",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("api_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("pool_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["api_id"], ["external_apis.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["pool_id"], ["proxy_pools.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "api_id", "account_id", name="uq_api_client_proxy_pool"
        ),
    )
    op.create_index(
        "ix_api_client_proxy_pool_api_id", "api_client_proxy_pool", ["api_id"]
    )
    op.create_index(
        "ix_api_client_proxy_pool_account_id",
        "api_client_proxy_pool",
        ["account_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_api_client_proxy_pool_account_id", table_name="api_client_proxy_pool"
    )
    op.drop_index(
        "ix_api_client_proxy_pool_api_id", table_name="api_client_proxy_pool"
    )
    op.drop_table("api_client_proxy_pool")

    op.drop_constraint("fk_proxies_account_id", "proxies", type_="foreignkey")
    op.drop_index("ix_proxies_account_id", table_name="proxies")
    op.drop_column("proxies", "account_id")

    op.drop_constraint(
        "uq_proxy_pools_account_name", "proxy_pools", type_="unique"
    )
    op.drop_index("ix_proxy_pools_name", table_name="proxy_pools")
    op.create_index(
        "ix_proxy_pools_name", "proxy_pools", ["name"], unique=True
    )
    op.drop_constraint(
        "fk_proxy_pools_account_id", "proxy_pools", type_="foreignkey"
    )
    op.drop_index("ix_proxy_pools_account_id", table_name="proxy_pools")
    op.drop_column("proxy_pools", "account_id")
