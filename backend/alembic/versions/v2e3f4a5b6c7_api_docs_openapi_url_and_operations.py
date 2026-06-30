"""api docs: openapi_url em external_apis + tabela api_doc_operations

Revision ID: v2e3f4a5b6c7
Revises: u1d2e3f4a5b6
Create Date: 2026-06-29 09:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "v2e3f4a5b6c7"
down_revision = "u1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "external_apis",
        sa.Column("openapi_url", sa.String(length=2048), nullable=True),
    )
    op.create_table(
        "api_doc_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("api_id", sa.Uuid(), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("summary", sa.String(length=512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("operation_json", sa.Text(), nullable=True),
        sa.Column("visible", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["api_id"], ["external_apis.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "api_id", "method", "path", name="uq_api_doc_op_api_method_path"
        ),
    )
    op.create_index("ix_api_doc_operations_api_id", "api_doc_operations", ["api_id"])


def downgrade() -> None:
    op.drop_index("ix_api_doc_operations_api_id", table_name="api_doc_operations")
    op.drop_table("api_doc_operations")
    op.drop_column("external_apis", "openapi_url")
