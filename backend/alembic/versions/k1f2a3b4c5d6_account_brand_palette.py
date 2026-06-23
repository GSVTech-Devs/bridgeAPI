"""account brand palette

Expande a cor de marca única para uma paleta de três cores:
- renomeia ``brand_color`` -> ``brand_primary``
- adiciona ``brand_secondary`` e ``brand_tertiary`` (hex ``#rrggbb``).

Revision ID: k1f2a3b4c5d6
Revises: j0e1f2a3b4c5
Create Date: 2026-06-22 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "k1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "j0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("accounts", "brand_color", new_column_name="brand_primary")
    op.add_column(
        "accounts", sa.Column("brand_secondary", sa.String(7), nullable=True)
    )
    op.add_column(
        "accounts", sa.Column("brand_tertiary", sa.String(7), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("accounts", "brand_tertiary")
    op.drop_column("accounts", "brand_secondary")
    op.alter_column("accounts", "brand_primary", new_column_name="brand_color")
