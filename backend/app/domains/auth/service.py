from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.domains.auth.models import User, UserRole


class DuplicateEmailError(Exception):
    pass


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


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
