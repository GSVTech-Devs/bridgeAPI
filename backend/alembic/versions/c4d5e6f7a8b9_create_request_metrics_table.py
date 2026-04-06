"""create request_metrics table

Revision ID: c4d5e6f7a8b9
Revises: f3c2d1b4e5a6
Create Date: 2026-04-02 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "f3c2d1b4e5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "request_metrics",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("api_id", sa.UUID(), nullable=False),
        sa.Column("key_id", sa.UUID(), nullable=False),
        sa.Column("path", sa.String(2048), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("cost", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["api_id"], ["external_apis.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["key_id"], ["api_keys.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_request_metrics_client_id", "request_metrics", ["client_id"])
    op.create_index("ix_request_metrics_api_id", "request_metrics", ["api_id"])
    op.create_index("ix_request_metrics_key_id", "request_metrics", ["key_id"])
    op.create_index("ix_request_metrics_created_at", "request_metrics", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_request_metrics_created_at", table_name="request_metrics")
    op.drop_index("ix_request_metrics_key_id", table_name="request_metrics")
    op.drop_index("ix_request_metrics_api_id", table_name="request_metrics")
    op.drop_index("ix_request_metrics_client_id", table_name="request_metrics")
    op.drop_table("request_metrics")
