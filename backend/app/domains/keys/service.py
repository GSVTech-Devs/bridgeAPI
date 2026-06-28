from __future__ import annotations

import secrets
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    decrypt_value,
    encrypt_value,
    hash_password,
    verify_password,
)
from app.domains.accounts.models import AccountStatus
from app.domains.accounts.service import AccountNotFoundError, get_account_by_id
from app.domains.keys.models import APIKey, APIKeyStatus
from app.domains.permissions.models import Permission

MAX_KEYS_PER_ACCOUNT_PER_API = 5
MAX_GLOBAL_KEYS_PER_ACCOUNT = 5


class APIKeyNotFoundError(Exception):
    pass


class UnauthorizedApiError(Exception):
    pass


class APIKeyLimitExceededError(Exception):
    pass


async def _require_active_account(db: AsyncSession, account_id: uuid.UUID):
    account = await get_account_by_id(db, str(account_id))
    if account.status != AccountStatus.ACTIVE:
        raise AccountNotFoundError(f"Account is not active: {account_id}")
    return account


async def create_api_key(
    db: AsyncSession, account_id: uuid.UUID, name: str, *, api_id: uuid.UUID
) -> tuple[APIKey, str]:
    await _require_active_account(db, account_id)

    perm_result = await db.execute(
        select(Permission).where(
            Permission.account_id == account_id,
            Permission.api_id == api_id,
            Permission.revoked_at.is_(None),
        )
    )
    if perm_result.scalar_one_or_none() is None:
        raise UnauthorizedApiError(f"Account has no active permission for API {api_id}")

    count_result = await db.execute(
        select(func.count())
        .select_from(APIKey)
        .where(
            APIKey.account_id == account_id,
            APIKey.api_id == api_id,
            APIKey.status == APIKeyStatus.ACTIVE,
        )
    )
    if count_result.scalar_one() >= MAX_KEYS_PER_ACCOUNT_PER_API:
        raise APIKeyLimitExceededError(
            f"Maximum of {MAX_KEYS_PER_ACCOUNT_PER_API} active keys per API reached"
        )

    return await _persist_api_key(db, account_id, name, api_id=api_id)


async def create_global_api_key(
    db: AsyncSession, account_id: uuid.UUID, name: str
) -> tuple[APIKey, str]:
    """Cria uma chave *global* (``api_id`` nulo) para a conta.

    Uma chave global autentica para qualquer API que a conta tenha permissão
    ativa de consumir (a checagem de ``Permission`` continua acontecendo por
    requisição no proxy). Por isso não há checagem de permissão por API aqui.
    O limite é por conta e independente do limite de chaves por API.
    """
    await _require_active_account(db, account_id)

    count_result = await db.execute(
        select(func.count())
        .select_from(APIKey)
        .where(
            APIKey.account_id == account_id,
            APIKey.api_id.is_(None),
            APIKey.status == APIKeyStatus.ACTIVE,
        )
    )
    if count_result.scalar_one() >= MAX_GLOBAL_KEYS_PER_ACCOUNT:
        raise APIKeyLimitExceededError(
            f"Maximum of {MAX_GLOBAL_KEYS_PER_ACCOUNT} active global keys reached"
        )

    return await _persist_api_key(db, account_id, name, api_id=None)


async def _persist_api_key(
    db: AsyncSession,
    account_id: uuid.UUID,
    name: str,
    *,
    api_id: uuid.UUID | None,
) -> tuple[APIKey, str]:
    key_prefix = secrets.token_hex(4)
    raw_secret = f"brg_{key_prefix}_{secrets.token_urlsafe(24)}"

    api_key = APIKey(
        account_id=account_id,
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


async def list_api_keys(
    db: AsyncSession, account_id: uuid.UUID
) -> list[tuple[APIKey, str | None]]:
    result = await db.execute(select(APIKey).where(APIKey.account_id == account_id))
    keys = list(result.scalars().all())
    return [
        (k, decrypt_value(k.key_secret_encrypted) if k.key_secret_encrypted else None)
        for k in keys
    ]


async def revoke_api_key(
    db: AsyncSession, account_id: uuid.UUID, key_id: str
) -> APIKey:
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == key_id,
            APIKey.account_id == account_id,
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
