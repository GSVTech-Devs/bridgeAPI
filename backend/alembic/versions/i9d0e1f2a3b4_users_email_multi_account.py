"""users email per-account (one email, multiple companies)

Permite que o mesmo email tenha acesso a várias accounts: o email deixa de ser
globalmente único e passa a ser único apenas por ``(email, account_id)``.

Revision ID: i9d0e1f2a3b4
Revises: h8c9d0e1f2a3
Create Date: 2026-06-22 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "h8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # email deixa de ser único globalmente (mantém só o índice de busca)
    op.drop_index("ix_users_email", table_name="users")
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    # unicidade real: um email no máximo uma vez por account
    op.create_unique_constraint(
        "uq_user_email_account", "users", ["email", "account_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_user_email_account", "users", type_="unique")
    op.drop_index("ix_users_email", table_name="users")
    op.create_index("ix_users_email", "users", ["email"], unique=True)
