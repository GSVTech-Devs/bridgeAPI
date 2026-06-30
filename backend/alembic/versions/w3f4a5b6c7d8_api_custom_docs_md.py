"""api custom docs: coluna custom_docs_md em external_apis

Revision ID: w3f4a5b6c7d8
Revises: v2e3f4a5b6c7
Create Date: 2026-06-30 12:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "w3f4a5b6c7d8"
down_revision = "v2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "external_apis",
        sa.Column("custom_docs_md", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("external_apis", "custom_docs_md")
