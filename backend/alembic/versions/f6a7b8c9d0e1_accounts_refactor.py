"""accounts refactor: split clients into accounts + users

- cria a tabela ``accounts`` (sucede ``clients``)
- adiciona ``users.account_id`` e migra cada client para account + owner
- renomeia ``client_id`` -> ``account_id`` em api_keys/permissions/request_metrics
- dropa a tabela ``clients``

Os ids são preservados (account.id = client.id), então as FKs apenas trocam
de alvo sem reescrever valores.

Revision ID: f6a7b8c9d0e1
Revises: e1f2a3b4c5d6
Create Date: 2026-06-19 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tabela accounts
    op.create_table(
        "accounts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(20), nullable=False, server_default="individual"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_accounts_type", "accounts", ["type"])
    op.create_index("ix_accounts_status", "accounts", ["status"])

    # 2. users.account_id
    op.add_column("users", sa.Column("account_id", sa.UUID(), nullable=True))
    op.create_index("ix_users_account_id", "users", ["account_id"])
    op.create_foreign_key(
        "users_account_id_fkey", "users", "accounts", ["account_id"], ["id"]
    )

    # 3. Migração de dados: cada client -> account(individual) + user(owner)
    op.execute("""
        INSERT INTO accounts (id, name, type, status, created_at)
        SELECT id, name, 'individual',
               CASE WHEN status = 'blocked' THEN 'blocked' ELSE 'active' END,
               created_at
        FROM clients
        """)
    op.execute("""
        INSERT INTO users (id, email, password_hash, role, account_id, created_at)
        SELECT gen_random_uuid(), c.email, c.password_hash, 'owner', c.id, c.created_at
        FROM clients c
        WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.email = c.email)
        """)

    # 4. Reaponta client_id -> account_id (mesmo valor de id já existe em accounts)
    for table in ("api_keys", "permissions", "request_metrics"):
        op.drop_constraint(f"{table}_client_id_fkey", table, type_="foreignkey")

    op.drop_constraint("uq_permission_client_api", "permissions", type_="unique")

    op.drop_index("ix_api_keys_client_id", table_name="api_keys")
    op.drop_index("ix_permissions_client_id", table_name="permissions")
    op.drop_index("ix_request_metrics_client_id", table_name="request_metrics")

    op.alter_column("api_keys", "client_id", new_column_name="account_id")
    op.alter_column("permissions", "client_id", new_column_name="account_id")
    op.alter_column("request_metrics", "client_id", new_column_name="account_id")

    op.create_index("ix_api_keys_account_id", "api_keys", ["account_id"])
    op.create_index("ix_permissions_account_id", "permissions", ["account_id"])
    op.create_index("ix_request_metrics_account_id", "request_metrics", ["account_id"])

    op.create_unique_constraint(
        "uq_permission_account_api", "permissions", ["account_id", "api_id"]
    )

    for table in ("api_keys", "permissions", "request_metrics"):
        op.create_foreign_key(
            f"{table}_account_id_fkey", table, "accounts", ["account_id"], ["id"]
        )

    # 5. Dropa clients
    op.drop_index("ix_clients_status", table_name="clients")
    op.drop_index("ix_clients_email", table_name="clients")
    op.drop_table("clients")


def downgrade() -> None:
    # Recria clients (lossy: usa o e-mail do owner de cada account)
    op.create_table(
        "clients",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clients_email", "clients", ["email"], unique=True)
    op.create_index("ix_clients_status", "clients", ["status"])

    op.execute("""
        INSERT INTO clients (id, name, email, password_hash, status, created_at)
        SELECT a.id, a.name,
               COALESCE(u.email, a.id::text || '@migrated.local'),
               COALESCE(u.password_hash, ''),
               a.status, a.created_at
        FROM accounts a
        LEFT JOIN users u ON u.account_id = a.id AND u.role = 'owner'
        """)

    # Reverte FKs/colunas account_id -> client_id
    for table in ("api_keys", "permissions", "request_metrics"):
        op.drop_constraint(f"{table}_account_id_fkey", table, type_="foreignkey")

    op.drop_constraint("uq_permission_account_api", "permissions", type_="unique")

    op.drop_index("ix_api_keys_account_id", table_name="api_keys")
    op.drop_index("ix_permissions_account_id", table_name="permissions")
    op.drop_index("ix_request_metrics_account_id", table_name="request_metrics")

    op.alter_column("api_keys", "account_id", new_column_name="client_id")
    op.alter_column("permissions", "account_id", new_column_name="client_id")
    op.alter_column("request_metrics", "account_id", new_column_name="client_id")

    op.create_index("ix_api_keys_client_id", "api_keys", ["client_id"])
    op.create_index("ix_permissions_client_id", "permissions", ["client_id"])
    op.create_index("ix_request_metrics_client_id", "request_metrics", ["client_id"])

    op.create_unique_constraint(
        "uq_permission_client_api", "permissions", ["client_id", "api_id"]
    )

    for table in ("api_keys", "permissions", "request_metrics"):
        op.create_foreign_key(
            f"{table}_client_id_fkey", table, "clients", ["client_id"], ["id"]
        )

    # Remove owners migrados e a coluna/tabela accounts
    op.execute("DELETE FROM users WHERE role = 'owner' AND account_id IS NOT NULL")
    op.drop_constraint("users_account_id_fkey", "users", type_="foreignkey")
    op.drop_index("ix_users_account_id", table_name="users")
    op.drop_column("users", "account_id")

    op.drop_index("ix_accounts_status", table_name="accounts")
    op.drop_index("ix_accounts_type", table_name="accounts")
    op.drop_table("accounts")
