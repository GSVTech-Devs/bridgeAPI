from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.domains.auth.models import User, UserRole


class DuplicateEmailError(Exception):
    pass


class InvalidCurrentPasswordError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


async def get_users_by_email(db: AsyncSession, email: str) -> list[User]:
    """Todas as linhas (vínculos a accounts) de um email — a "identidade"."""
    result = await db.execute(
        select(User).where(User.email == email).order_by(User.created_at.asc())
    )
    return list(result.scalars().all())


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Uma linha qualquer do email (compat). Use ``get_users_by_email`` quando
    precisar de todos os vínculos."""
    users = await get_users_by_email(db, email)
    return users[0] if users else None


async def get_account_user(
    db: AsyncSession, account_id: uuid.UUID | str, email: str
) -> User | None:
    """Linha do email dentro de uma account específica (se existir)."""
    result = await db.execute(
        select(User).where(User.account_id == account_id, User.email == email)
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID | str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def set_password_for_email(
    db: AsyncSession, email: str, new_password: str, *, commit: bool = True
) -> None:
    """Aplica uma nova senha a **todas** as linhas do email.

    Mantém a invariante "um email, uma senha": como a mesma pessoa pode estar
    vinculada a várias accounts, a credencial é compartilhada por todas elas.
    """
    new_hash = hash_password(new_password)
    for user in await get_users_by_email(db, email):
        user.password_hash = new_hash
    if commit:
        await db.commit()


async def change_user_password(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | str,
    current_password: str,
    new_password: str,
) -> User:
    """Troca a senha do próprio usuário, validando a senha atual.

    A troca propaga para todos os vínculos do mesmo email (identidade única).
    """
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise UserNotFoundError(f"User not found: {user_id}")
    if not verify_password(current_password, user.password_hash):
        raise InvalidCurrentPasswordError("Current password is incorrect")
    await set_password_for_email(db, user.email, new_password)
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    """Autentica pelo email; retorna uma linha qualquer da identidade.

    Como todas as linhas de um email compartilham a senha, basta verificar
    contra a primeira."""
    users = await get_users_by_email(db, email)
    if not users or not verify_password(password, users[0].password_hash):
        return None
    return users[0]


async def create_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    role: str = UserRole.OWNER,
    account_id: Optional[uuid.UUID] = None,
    commit: bool = True,
) -> User:
    if await get_user_by_email(db, email) is not None:
        raise DuplicateEmailError(f"Email already registered: {email}")
    user = User(
        email=email,
        password_hash=hash_password(password),
        role=role,
        account_id=account_id,
    )
    db.add(user)
    if commit:
        await db.commit()
        await db.refresh(user)
    return user
