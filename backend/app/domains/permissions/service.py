from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.accounts.models import Account
from app.domains.apis.models import ExternalAPI
from app.domains.permissions.models import Permission


class DuplicatePermissionError(Exception):
    pass


class PermissionNotFoundError(Exception):
    pass


async def grant_permission(
    db: AsyncSession, account_id: str, api_id: str
) -> Permission:
    result = await db.execute(
        select(Permission).where(
            Permission.account_id == uuid.UUID(account_id),
            Permission.api_id == uuid.UUID(api_id),
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        if existing.revoked_at is None:
            raise DuplicatePermissionError(
                f"Permission already exists for account {account_id} and api {api_id}"
            )
        existing.revoked_at = None
        existing.granted_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(existing)
        return existing

    permission = Permission(
        account_id=uuid.UUID(account_id),
        api_id=uuid.UUID(api_id),
        granted_at=datetime.now(timezone.utc),
    )
    db.add(permission)
    await db.commit()
    await db.refresh(permission)
    return permission


async def revoke_permission(
    db: AsyncSession, account_id: str, api_id: str
) -> Permission:
    result = await db.execute(
        select(Permission).where(
            Permission.account_id == uuid.UUID(account_id),
            Permission.api_id == uuid.UUID(api_id),
            Permission.revoked_at.is_(None),
        )
    )
    permission = result.scalar_one_or_none()
    if permission is None:
        raise PermissionNotFoundError(
            f"Active permission not found for account {account_id} and api {api_id}"
        )

    permission.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    return permission


async def list_permissions(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(
            Permission.account_id,
            Permission.api_id,
            Account.name.label("account_name"),
            ExternalAPI.name.label("api_name"),
            Permission.revoked_at,
        )
        .join(Account, Account.id == Permission.account_id)
        .join(ExternalAPI, ExternalAPI.id == Permission.api_id)
    )
    rows = result.fetchall()
    return [
        {
            "account_id": str(r.account_id),
            "api_id": str(r.api_id),
            "account_name": r.account_name,
            "api_name": r.api_name,
            "status": "revoked" if r.revoked_at is not None else "active",
        }
        for r in rows
    ]


async def get_account_authorized_apis(
    db: AsyncSession, account_id: uuid.UUID
) -> list[ExternalAPI]:
    result = await db.execute(
        select(ExternalAPI)
        .join(Permission, Permission.api_id == ExternalAPI.id)
        .where(
            Permission.account_id == account_id,
            Permission.revoked_at.is_(None),
        )
    )
    return list(result.scalars().all())
