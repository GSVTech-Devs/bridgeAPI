"""add on delete cascade/set null to external_apis foreign keys

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-04-17 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f5a6b7c8d9e0"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # endpoints.api_id → CASCADE (endpoint sem API não faz sentido)
    op.drop_constraint("endpoints_api_id_fkey", "endpoints", type_="foreignkey")
    op.create_foreign_key(
        "endpoints_api_id_fkey",
        "endpoints", "external_apis",
        ["api_id"], ["id"],
        ondelete="CASCADE",
    )

    # permissions.api_id → CASCADE (permissão de API deletada deve ser removida)
    op.drop_constraint("permissions_api_id_fkey", "permissions", type_="foreignkey")
    op.create_foreign_key(
        "permissions_api_id_fkey",
        "permissions", "external_apis",
        ["api_id"], ["id"],
        ondelete="CASCADE",
    )

    # api_keys.api_id → SET NULL (chave fica mas sem vínculo com a API deletada)
    op.drop_constraint("api_keys_api_id_fkey", "api_keys", type_="foreignkey")
    op.create_foreign_key(
        "api_keys_api_id_fkey",
        "api_keys", "external_apis",
        ["api_id"], ["id"],
        ondelete="SET NULL",
    )

    # request_metrics.api_id → SET NULL (histórico preservado sem o vínculo)
    op.drop_constraint("request_metrics_api_id_fkey", "request_metrics", type_="foreignkey")
    op.create_foreign_key(
        "request_metrics_api_id_fkey",
        "request_metrics", "external_apis",
        ["api_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("request_metrics_api_id_fkey", "request_metrics", type_="foreignkey")
    op.create_foreign_key(
        "request_metrics_api_id_fkey",
        "request_metrics", "external_apis",
        ["api_id"], ["id"],
    )

    op.drop_constraint("api_keys_api_id_fkey", "api_keys", type_="foreignkey")
    op.create_foreign_key(
        "api_keys_api_id_fkey",
        "api_keys", "external_apis",
        ["api_id"], ["id"],
    )

    op.drop_constraint("permissions_api_id_fkey", "permissions", type_="foreignkey")
    op.create_foreign_key(
        "permissions_api_id_fkey",
        "permissions", "external_apis",
        ["api_id"], ["id"],
    )

    op.drop_constraint("endpoints_api_id_fkey", "endpoints", type_="foreignkey")
    op.create_foreign_key(
        "endpoints_api_id_fkey",
        "endpoints", "external_apis",
        ["api_id"], ["id"],
    )
