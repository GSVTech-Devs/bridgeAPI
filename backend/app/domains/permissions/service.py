from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.apis.models import ExternalAPI
from app.domains.permissions.models import Permission


class DuplicatePermissionError(Exception):
    pass


class PermissionNotFoundError(Exception):
    pass


async def grant_permission(db: AsyncSession, client_id: str, api_id: str) -> Permission:
    result = await db.execute(
        select(Permission).where(
            Permission.client_id == uuid.UUID(client_id),
            Permission.api_id == uuid.UUID(api_id),
            Permission.revoked_at.is_(None),
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        raise DuplicatePermissionError(
            f"Permission already exists for client {client_id} and api {api_id}"
        )

    permission = Permission(
        client_id=uuid.UUID(client_id),
        api_id=uuid.UUID(api_id),
        granted_at=datetime.now(timezone.utc),
    )
    db.add(permission)
    await db.commit()
    await db.refresh(permission)
    return permission


async def revoke_permission(
    db: AsyncSession, client_id: str, api_id: str
) -> Permission:
    result = await db.execute(
        select(Permission).where(
            Permission.client_id == uuid.UUID(client_id),
            Permission.api_id == uuid.UUID(api_id),
            Permission.revoked_at.is_(None),
        )
    )
    permission = result.scalar_one_or_none()
    if permission is None:
        raise PermissionNotFoundError(
            f"Active permission not found for client {client_id} and api {api_id}"
        )

    permission.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    return permission


async def get_client_authorized_apis(
    db: AsyncSession, client_email: str
) -> list[ExternalAPI]:
    from app.domains.clients.service import get_client_by_email

    client = await get_client_by_email(db, client_email)
    result = await db.execute(
        select(ExternalAPI)
        .join(Permission, Permission.api_id == ExternalAPI.id)
        .where(
            Permission.client_id == client.id,
            Permission.revoked_at.is_(None),
        )
    )
    return list(result.scalars().all())
