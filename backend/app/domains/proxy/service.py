from __future__ import annotations

import time
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_value
from app.domains.accounts.models import Account, AccountStatus
from app.domains.apis.models import APIAuthType, APIStatus, ExternalAPI
from app.domains.apis.service import get_api_by_id
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
) -> tuple[APIKey, Account, ExternalAPI]:
    # 1. Valida a API key
    api_key = await authenticate_api_key(db, presented_key)
    if api_key is None:
        raise InvalidKeyError("Invalid or revoked API key")

    # 2. Valida a account
    result = await db.execute(select(Account).where(Account.id == api_key.account_id))
    account = result.scalar_one_or_none()
    if account is None or account.status != AccountStatus.ACTIVE:
        raise InactiveClientError(f"Account is not active: {api_key.account_id}")

    # 2b. Se a chave estiver vinculada a uma API específica, verifica correspondência
    if api_key.api_id is not None and str(api_key.api_id) != api_id:
        raise PermissionDeniedError(
            f"Key is bound to API {api_key.api_id}, not {api_id}"
        )

    # 3. Valida a API upstream
    api = await get_api_by_id(db, api_id)
    if api.status != APIStatus.ACTIVE:
        raise DisabledAPIError(f"API is disabled: {api_id}")

    # 4. Valida permissão
    perm_result = await db.execute(
        select(Permission).where(
            Permission.account_id == account.id,
            Permission.api_id == api.id,
            Permission.revoked_at.is_(None),
        )
    )
    if perm_result.scalar_one_or_none() is None:
        raise PermissionDeniedError(
            f"Account {account.id} has no permission for API {api.id}"
        )

    # 5. Verifica rate limit
    await check_rate_limit(str(api_key.id), api_key.rate_limit, redis)

    return api_key, account, api


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
    correlation_id: Optional[str] = None,
    client_id: Optional[str] = None,
) -> dict:
    """Filtra headers de entrada e injeta credencial da API upstream.

    Se url_template contém {token}, a credencial já vai na URL — não injeta no header.
    Propaga o correlation_id via X-Correlation-Id para que a API downstream
    correlacione seus logs estruturados com o gateway. Propaga também o cliente
    da chamada via X-Bridge-Client, para a API resolver proxy/captcha do cliente.
    """
    _STRIP = {
        "x-bridge-key",
        "x-bridge-client",
        "host",
        "content-length",
        "transfer-encoding",
    }
    headers = {k: v for k, v in incoming_headers.items() if k.lower() not in _STRIP}

    if correlation_id is not None:
        headers["x-correlation-id"] = correlation_id

    if client_id is not None:
        headers["x-bridge-client"] = client_id

    if api.master_key_encrypted is None:
        return headers

    # Token já está no URL template — não duplicar no header
    if api.url_template and "{token}" in api.url_template:
        return headers

    master_key = decrypt_value(api.master_key_encrypted)

    if api.auth_type == APIAuthType.API_KEY:
        headers["x-api-key"] = master_key
    elif api.auth_type == APIAuthType.BEARER:
        headers["authorization"] = f"Bearer {master_key}"
    elif api.auth_type == APIAuthType.BASIC:
        headers["authorization"] = f"Basic {master_key}"

    return headers


def _render_template(template: str, path: str, master_key: str) -> str:
    """Substitui {query} (o path/consulta do cliente) e {token} (master key)."""
    return template.replace("{query}", path.lstrip("/")).replace("{token}", master_key)


def _build_url_from_template(api: ExternalAPI, path: str) -> str:
    """Substitui {query} e {token} no url_template."""
    master_key = ""
    if api.master_key_encrypted:
        master_key = decrypt_value(api.master_key_encrypted)
    return _render_template(api.url_template, path, master_key)


async def forward_to_upstream(
    http_client: httpx.AsyncClient,
    api: ExternalAPI,
    path: str,
    method: str,
    headers: dict,
    params: dict,
    content: Optional[bytes],
) -> httpx.Response:
    if api.url_template:
        url = _build_url_from_template(api, path)
    else:
        base = str(api.base_url).rstrip("/")
        clean_path = path.lstrip("/")
        url = f"{base}/{clean_path}" if clean_path else base

    # Método com que a Bridge chama a upstream: o declarado no cadastro (API POST),
    # senão repassa o método do cliente.
    upstream_method = (api.request_method or method or "GET").upper()

    # Corpo: se a API define um template (API POST), renderiza {query}/{token};
    # senão repassa o body do cliente.
    body = content
    if api.request_body_template:
        master_key = (
            decrypt_value(api.master_key_encrypted) if api.master_key_encrypted else ""
        )
        body = _render_template(api.request_body_template, path, master_key).encode()
        # Garante content-type p/ a upstream (default JSON) sem sobrescrever o existente.
        if not any(k.lower() == "content-type" for k in headers):
            headers = {**headers, "content-type": "application/json"}

    response = await http_client.request(
        method=upstream_method,
        url=url,
        headers=headers,
        params=params,
        content=body,
    )
    return response
