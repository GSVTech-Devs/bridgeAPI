"""Helpers de seed compartilhados pelos testes de integração (modelo accounts)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.domains.accounts.models import Account, AccountStatus, AccountType
from app.domains.auth.models import User, UserRole


async def seed_account(
    db: AsyncSession,
    *,
    name: str = "Acme",
    email: str = "acme@example.com",
    type_: AccountType = AccountType.INDIVIDUAL,
    status: AccountStatus = AccountStatus.ACTIVE,
    password: str = "hunter2",
) -> tuple[Account, User]:
    """Cria uma account + usuário responsável (owner) e devolve ambos."""
    account = Account(name=name, type=type_, status=status)
    db.add(account)
    await db.flush()
    owner = User(
        email=email,
        password_hash=hash_password(password),
        role=UserRole.OWNER,
        account_id=account.id,
    )
    db.add(owner)
    await db.commit()
    await db.refresh(account)
    await db.refresh(owner)
    return account, owner


def account_headers(
    account_id, email: str = "acme@example.com", role: str = "owner"
) -> dict[str, str]:
    token = create_access_token(
        email,
        role=role,
        extra_claims={"user_id": str(uuid.uuid4()), "account_id": str(account_id)},
    )
    return {"Authorization": f"Bearer {token}"}


def admin_headers(email: str = "admin@bridge.com") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(email, role='admin')}"}
