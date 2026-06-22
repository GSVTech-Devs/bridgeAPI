"""account logo branding

Adiciona à tabela ``accounts`` as colunas de identidade visual do portal:
- ``logo_data`` (bytes da imagem)
- ``logo_content_type`` (mime type validado)

Revision ID: h8c9d0e1f2a3
Revises: g7b8c9d0e1f2
Create Date: 2026-06-22 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "h8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "g7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("logo_data", sa.LargeBinary(), nullable=True))
    op.add_column(
        "accounts", sa.Column("logo_content_type", sa.String(100), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("accounts", "logo_content_type")
    op.drop_column("accounts", "logo_data")
