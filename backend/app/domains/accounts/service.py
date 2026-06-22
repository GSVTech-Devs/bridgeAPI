from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domains.accounts.models import Account, AccountStatus, AccountType
from app.domains.auth.models import User, UserRole
from app.domains.auth.service import (
    DuplicateEmailError,
    get_users_by_email,
    set_password_for_email,
)


class AccountNotFoundError(Exception):
    pass


class OwnerNotFoundError(Exception):
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
    allow_existing: bool = False,
) -> tuple[Account, User]:
    # Quando ``allow_existing`` (empresas), um email já cadastrado pode virar
    # owner de outra account: reaproveitamos a senha da identidade (um email,
    # uma senha) e ignoramos a senha enviada. Email de admin nunca é reusado.
    existing = await get_users_by_email(db, owner_email)
    if existing and (
        not allow_existing or any(u.role == UserRole.ADMIN.value for u in existing)
    ):
        raise DuplicateEmailError(f"Email already registered: {owner_email}")
    password_hash = existing[0].password_hash if existing else hash_password(owner_password)

    account = Account(
        name=account_name,
        type=account_type,
        status=AccountStatus.ACTIVE,
    )
    db.add(account)
    await db.flush()  # garante account.id antes de vincular o usuário

    owner = User(
        email=owner_email,
        password_hash=password_hash,
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
        allow_existing=True,
    )


async def get_account_by_id(db: AsyncSession, account_id: str) -> Account:
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if account is None:
        raise AccountNotFoundError(f"Account not found: {account_id}")
    return account


async def get_account_owner(db: AsyncSession, account_id: str) -> User:
    """Retorna o usuário responsável (owner) da account."""
    result = await db.execute(
        select(User).where(
            User.account_id == account_id,
            User.role == UserRole.OWNER.value,
        )
    )
    owner = result.scalar_one_or_none()
    if owner is None:
        raise OwnerNotFoundError(f"Owner not found for account: {account_id}")
    return owner


async def update_account_credentials(
    db: AsyncSession,
    account_id: str,
    *,
    email: str | None = None,
    password: str | None = None,
) -> tuple[Account, User]:
    """Atualiza email e/ou senha de acesso do responsável da account."""
    account = await get_account_by_id(db, account_id)
    owner = await get_account_owner(db, account_id)

    if email is not None and email != owner.email:
        # Troca de email da identidade: o novo email não pode já pertencer a
        # outra identidade. Renomeia todas as linhas do email antigo (a mesma
        # pessoa pode estar em várias accounts).
        if await get_users_by_email(db, email):
            raise DuplicateEmailError(f"Email already registered: {email}")
        old_email = owner.email
        for user in await get_users_by_email(db, old_email):
            user.email = email

    if password is not None:
        # Propaga para todas as linhas do email (um email, uma senha).
        await set_password_for_email(db, owner.email, password, commit=False)

    await db.commit()
    await db.refresh(owner)
    return account, owner


async def list_accounts(
    db: AsyncSession, page: int = 1, per_page: int = 20
) -> tuple[list[tuple[Account, User | None]], int]:
    total = (await db.execute(select(func.count()).select_from(Account))).scalar_one()
    result = await db.execute(
        select(Account, User)
        .outerjoin(
            User,
            (User.account_id == Account.id) & (User.role == UserRole.OWNER.value),
        )
        .order_by(Account.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return [(row[0], row[1]) for row in result.all()], total


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
