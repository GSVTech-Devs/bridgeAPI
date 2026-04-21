from __future__ import annotations

import secrets
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_value, encrypt_value, hash_password, verify_password
from app.domains.clients.models import ClientStatus
from app.domains.clients.service import ClientNotFoundError, get_client_by_email
from app.domains.keys.models import APIKey, APIKeyStatus
from app.domains.permissions.models import Permission


MAX_KEYS_PER_CLIENT_PER_API = 5


class APIKeyNotFoundError(Exception):
    pass


class UnauthorizedApiError(Exception):
    pass


class APIKeyLimitExceededError(Exception):
    pass


async def create_api_key(
    db: AsyncSession, client_email: str, name: str, *, api_id: uuid.UUID
) -> tuple[APIKey, str]:
    client = await get_client_by_email(db, client_email)
    if client.status != ClientStatus.ACTIVE:
        raise ClientNotFoundError(f"Client is not active: {client_email}")

    perm_result = await db.execute(
        select(Permission).where(
            Permission.client_id == client.id,
            Permission.api_id == api_id,
            Permission.revoked_at.is_(None),
        )
    )
    if perm_result.scalar_one_or_none() is None:
        raise UnauthorizedApiError(f"Client has no active permission for API {api_id}")

    count_result = await db.execute(
        select(func.count()).select_from(APIKey).where(
            APIKey.client_id == client.id,
            APIKey.api_id == api_id,
            APIKey.status == APIKeyStatus.ACTIVE,
        )
    )
    if count_result.scalar_one() >= MAX_KEYS_PER_CLIENT_PER_API:
        raise APIKeyLimitExceededError(
            f"Maximum of {MAX_KEYS_PER_CLIENT_PER_API} active keys per API reached"
        )

    key_prefix = secrets.token_hex(4)
    raw_secret = f"brg_{key_prefix}_{secrets.token_urlsafe(24)}"

    api_key = APIKey(
        client_id=client.id,
        api_id=api_id,
        name=name,
        key_prefix=key_prefix,
        key_secret_hash=hash_password(raw_secret),
        key_secret_encrypted=encrypt_value(raw_secret),
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return api_key, raw_secret


async def list_api_keys(db: AsyncSession, client_email: str) -> list[tuple[APIKey, str | None]]:
    client = await get_client_by_email(db, client_email)
    result = await db.execute(select(APIKey).where(APIKey.client_id == client.id))
    keys = list(result.scalars().all())
    return [
        (k, decrypt_value(k.key_secret_encrypted) if k.key_secret_encrypted else None)
        for k in keys
    ]


async def revoke_api_key(db: AsyncSession, client_email: str, key_id: str) -> APIKey:
    client = await get_client_by_email(db, client_email)
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == key_id,
            APIKey.client_id == client.id,
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise APIKeyNotFoundError(f"API key not found: {key_id}")

    api_key.status = APIKeyStatus.REVOKED
    await db.commit()
    await db.refresh(api_key)
    return api_key


async def authenticate_api_key(db: AsyncSession, presented_key: str) -> APIKey | None:
    if not presented_key.startswith("brg_"):
        return None

    parts = presented_key.split("_", 2)
    if len(parts) != 3:
        return None

    key_prefix = parts[1]
    result = await db.execute(select(APIKey).where(APIKey.key_prefix == key_prefix))
    api_key = result.scalar_one_or_none()
    if api_key is None or api_key.status != APIKeyStatus.ACTIVE:
        return None
    if not verify_password(presented_key, api_key.key_secret_hash):
        return None
    return api_key
