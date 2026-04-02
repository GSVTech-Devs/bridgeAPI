"""create clients table

Revision ID: 76f693953ed4
Revises: 806d0ec16460
Create Date: 2026-04-02 11:50:21.105664

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "76f693953ed4"
down_revision: Union[str, Sequence[str], None] = "806d0ec16460"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "clients",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clients_email", "clients", ["email"], unique=True)
    op.create_index("ix_clients_status", "clients", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_clients_status", table_name="clients")
    op.drop_index("ix_clients_email", table_name="clients")
    op.drop_table("clients")
