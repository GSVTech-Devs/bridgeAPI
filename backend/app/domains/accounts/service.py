from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domains.accounts.models import Account, AccountStatus, AccountType
from app.domains.auth.models import User, UserRole
from app.domains.auth.service import DuplicateEmailError, get_user_by_email


class AccountNotFoundError(Exception):
    pass


class InvalidStatusTransitionError(Exception):
    pass


async def _create_account_with_owner(
    db: AsyncSession,
    *,
    account_name: str,
    account_type: AccountType,
    owner_email: str,
    owner_password: str,
) -> tuple[Account, User]:
    if await get_user_by_email(db, owner_email) is not None:
        raise DuplicateEmailError(f"Email already registered: {owner_email}")

    account = Account(
        name=account_name,
        type=account_type,
        status=AccountStatus.ACTIVE,
    )
    db.add(account)
    await db.flush()  # garante account.id antes de vincular o usuário

    owner = User(
        email=owner_email,
        password_hash=hash_password(owner_password),
        role=UserRole.OWNER,
        account_id=account.id,
    )
    db.add(owner)
    await db.commit()
    await db.refresh(account)
    await db.refresh(owner)
    return account, owner


async def create_individual(
    db: AsyncSession, *, name: str, email: str, password: str
) -> tuple[Account, User]:
    """Usuário avulso: account individual com um único usuário responsável."""
    return await _create_account_with_owner(
        db,
        account_name=name,
        account_type=AccountType.INDIVIDUAL,
        owner_email=email,
        owner_password=password,
    )


async def create_company(
    db: AsyncSession, *, company_name: str, owner_email: str, owner_password: str
) -> tuple[Account, User]:
    """Empresa: account company com um usuário responsável inicial."""
    return await _create_account_with_owner(
        db,
        account_name=company_name,
        account_type=AccountType.COMPANY,
        owner_email=owner_email,
        owner_password=owner_password,
    )


async def get_account_by_id(db: AsyncSession, account_id: str) -> Account:
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if account is None:
        raise AccountNotFoundError(f"Account not found: {account_id}")
    return account


async def list_accounts(
    db: AsyncSession, page: int = 1, per_page: int = 20
) -> tuple[list[Account], int]:
    total = (await db.execute(select(func.count()).select_from(Account))).scalar_one()
    result = await db.execute(
        select(Account)
        .order_by(Account.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return list(result.scalars().all()), total


async def block_account(db: AsyncSession, account_id: str) -> Account:
    account = await get_account_by_id(db, account_id)
    if account.status == AccountStatus.BLOCKED:
        raise InvalidStatusTransitionError("Account is already blocked")
    account.status = AccountStatus.BLOCKED
    await db.commit()
    await db.refresh(account)
    return account


async def unblock_account(db: AsyncSession, account_id: str) -> Account:
    account = await get_account_by_id(db, account_id)
    if account.status != AccountStatus.BLOCKED:
        raise InvalidStatusTransitionError(
            f"Cannot unblock account with status: {account.status}"
        )
    account.status = AccountStatus.ACTIVE
    await db.commit()
    await db.refresh(account)
    return account
