from __future__ import annotations

import time
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_value
from app.domains.apis.models import APIAuthType, APIStatus, ExternalAPI
from app.domains.apis.service import get_api_by_id
from app.domains.clients.models import Client, ClientStatus
from app.domains.keys.models import APIKey
from app.domains.keys.service import authenticate_api_key
from app.domains.permissions.models import Permission


class InvalidKeyError(Exception):
    pass


class InactiveClientError(Exception):
    pass


class DisabledAPIError(Exception):
    pass


class PermissionDeniedError(Exception):
    pass


class RateLimitExceededError(Exception):
    pass


async def validate_request(
    db: AsyncSession,
    presented_key: str,
    api_id: str,
    redis=None,
) -> tuple[APIKey, Client, ExternalAPI]:
    # 1. Valida a API key
    api_key = await authenticate_api_key(db, presented_key)
    if api_key is None:
        raise InvalidKeyError("Invalid or revoked API key")

    # 2. Valida o cliente
    result = await db.execute(select(Client).where(Client.id == api_key.client_id))
    client = result.scalar_one_or_none()
    if client is None or client.status != ClientStatus.ACTIVE:
        raise InactiveClientError(f"Client is not active: {api_key.client_id}")

    # 3. Valida a API upstream
    api = await get_api_by_id(db, api_id)
    if api.status != APIStatus.ACTIVE:
        raise DisabledAPIError(f"API is disabled: {api_id}")

    # 4. Valida permissão
    perm_result = await db.execute(
        select(Permission).where(
            Permission.client_id == client.id,
            Permission.api_id == api.id,
            Permission.revoked_at.is_(None),
        )
    )
    if perm_result.scalar_one_or_none() is None:
        raise PermissionDeniedError(
            f"Client {client.id} has no permission for API {api.id}"
        )

    # 5. Verifica rate limit
    await check_rate_limit(str(api_key.id), api_key.rate_limit, redis)

    return api_key, client, api


async def check_rate_limit(
    key_id: str,
    rate_limit: int = 60,
    redis=None,
) -> None:
    """Sliding window rate limit usando sorted sets do Redis.

    Usa uma janela de 60 segundos. Falha aberta (fail open) se Redis
    estiver indisponível — o serviço não é derrubado por problemas no Redis.
    """
    if redis is None:
        return

    now = time.time()
    window_start = now - 60
    redis_key = f"rate_limit:{key_id}"

    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(redis_key, "-inf", window_start)
            pipe.zadd(redis_key, {str(now): now})
            pipe.zcard(redis_key)
            pipe.expire(redis_key, 60)
            results = await pipe.execute()

        count = results[2]
        if count > rate_limit:
            raise RateLimitExceededError(
                f"Rate limit exceeded: {count}/{rate_limit} req/min"
            )
    except RateLimitExceededError:
        raise
    except Exception:
        # Redis indisponível — fail open para não derrubar o serviço
        pass


def build_upstream_headers(
    api: ExternalAPI,
    incoming_headers: dict,
) -> dict:
    """Filtra headers de entrada e injeta credencial da API upstream."""
    _STRIP = {"x-bridge-key", "host", "content-length", "transfer-encoding"}
    headers = {k: v for k, v in incoming_headers.items() if k.lower() not in _STRIP}

    if api.master_key_encrypted is None:
        return headers

    master_key = decrypt_value(api.master_key_encrypted)

    if api.auth_type == APIAuthType.API_KEY:
        headers["x-api-key"] = master_key
    elif api.auth_type == APIAuthType.BEARER:
        headers["authorization"] = f"Bearer {master_key}"
    elif api.auth_type == APIAuthType.BASIC:
        headers["authorization"] = f"Basic {master_key}"

    return headers


async def forward_to_upstream(
    http_client: httpx.AsyncClient,
    api: ExternalAPI,
    path: str,
    method: str,
    headers: dict,
    params: dict,
    content: Optional[bytes],
) -> httpx.Response:
    base = str(api.base_url).rstrip("/")
    clean_path = path.lstrip("/")
    url = f"{base}/{clean_path}" if clean_path else base

    response = await http_client.request(
        method=method,
        url=url,
        headers=headers,
        params=params,
        content=content,
    )
    return response
