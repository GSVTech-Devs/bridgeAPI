"""account roles and member role_id

- cria a tabela ``account_roles`` (roles customizadas por account)
- adiciona ``users.role_id`` (FK opcional para a role do membro)

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-22 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "g7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "account_roles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "capabilities",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "name", name="uq_account_role_name"),
    )
    op.create_index("ix_account_roles_account_id", "account_roles", ["account_id"])

    op.add_column("users", sa.Column("role_id", sa.UUID(), nullable=True))
    op.create_index("ix_users_role_id", "users", ["role_id"])
    op.create_foreign_key(
        "users_role_id_fkey", "users", "account_roles", ["role_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("users_role_id_fkey", "users", type_="foreignkey")
    op.drop_index("ix_users_role_id", table_name="users")
    op.drop_column("users", "role_id")

    op.drop_index("ix_account_roles_account_id", table_name="account_roles")
    op.drop_table("account_roles")
