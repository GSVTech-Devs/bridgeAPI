"""account brand theme json

Substitui as 3 colunas de cor (``brand_primary``/``brand_secondary``/
``brand_tertiary``) por uma única coluna JSON ``brand_theme`` que guarda a
paleta por modo (claro/escuro), incluindo a cor de fundo:

    {"light": {"primary": "#..", "secondary": "#..", "tertiary": "#..",
               "background": "#.."},
     "dark":  {...}}

Cada valor é opcional (ausente/None = cor padrão do tema).

Revision ID: l2a3b4c5d6e7
Revises: k1f2a3b4c5d6
Create Date: 2026-06-22 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "l2a3b4c5d6e7"
down_revision: Union[str, Sequence[str], None] = "k1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("brand_theme", sa.JSON(), nullable=True))
    op.drop_column("accounts", "brand_primary")
    op.drop_column("accounts", "brand_secondary")
    op.drop_column("accounts", "brand_tertiary")


def downgrade() -> None:
    op.add_column(
        "accounts", sa.Column("brand_tertiary", sa.String(7), nullable=True)
    )
    op.add_column(
        "accounts", sa.Column("brand_secondary", sa.String(7), nullable=True)
    )
    op.add_column("accounts", sa.Column("brand_primary", sa.String(7), nullable=True))
    op.drop_column("accounts", "brand_theme")
