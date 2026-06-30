"""request_metrics.api_id nullable (corrige ON DELETE SET NULL)

A FK request_metrics.api_id usa ON DELETE SET NULL (histórico preservado sem o
vínculo), mas a coluna era NOT NULL — contradição que fazia o DELETE de uma API
com métricas falhar com NotNullViolation. Torna a coluna nullable, alinhando com
api_keys.api_id (mesmo intento).

Revision ID: x4a5b6c7d8e9
Revises: w3f4a5b6c7d8
Create Date: 2026-06-30 14:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "x4a5b6c7d8e9"
down_revision = "w3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "request_metrics",
        "api_id",
        existing_type=sa.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    # Reverter exige que não haja métricas órfãs (api_id NULL) na tabela.
    op.alter_column(
        "request_metrics",
        "api_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
