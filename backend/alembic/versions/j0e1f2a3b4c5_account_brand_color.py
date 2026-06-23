"""account brand color

Adiciona à tabela ``accounts`` a cor de marca do portal:
- ``brand_color`` (hex ``#rrggbb``) usada para gerar o tema do painel.

Revision ID: j0e1f2a3b4c5
Revises: i9d0e1f2a3b4
Create Date: 2026-06-22 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "j0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "i9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("brand_color", sa.String(7), nullable=True))


def downgrade() -> None:
    op.drop_column("accounts", "brand_color")
