from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_value, encrypt_value
from app.domains.apis.models import ExternalAPI
from app.domains.apis.service import APINotFoundError, get_api_by_id
from app.domains.proxies.models import (
    ApiClientProxyPool,
    Proxy,
    ProxyPool,
    ProxyStatus,
)
from app.domains.proxies.schemas import (
    ProxyConfigItem,
    ProxyConfigResponse,
    ProxyResponse,
)

# Sentinela para distinguir "sem filtro de dono" (admin vê tudo) de
# account_id=None (filtra só os da plataforma).
_ANY_ACCOUNT = object()


class ProxyNotFoundError(Exception):
    pass


class ProxyPoolNotFoundError(Exception):
    pass


class DuplicatePoolNameError(Exception):
    pass


# --------------------------------------------------------------------- helpers
def to_response(proxy: Proxy) -> ProxyResponse:
    return ProxyResponse(
        id=proxy.id,
        account_id=proxy.account_id,
        pool_id=proxy.pool_id,
        name=proxy.name,
        provider=proxy.provider,
        ownership=proxy.ownership,
        type=proxy.type,
        scheme=proxy.scheme,
        host=proxy.host,
        port=proxy.port,
        username=decrypt_value(proxy.username_encrypted)
        if proxy.username_encrypted
        else None,
        has_password=proxy.password_encrypted is not None,
        rotation=proxy.rotation,
        session_ttl_s=proxy.session_ttl_s,
        status=proxy.status,
        priority=proxy.priority,
        last_error=proxy.last_error,
        last_error_at=proxy.last_error_at,
        created_at=proxy.created_at,
    )


def _account_filter(column, account_id):
    """``account_id is None`` filtra os da plataforma (IS NULL); um UUID filtra
    aquele dono. ``_ANY_ACCOUNT`` (default) não filtra nada (visão admin)."""
    if account_id is _ANY_ACCOUNT:
        return None
    if account_id is None:
        return column.is_(None)
    return column == uuid.UUID(str(account_id))


# ----------------------------------------------------------------------- pools
async def create_pool(
    db: AsyncSession,
    name: str,
    description: str | None = None,
    account_id=None,
) -> ProxyPool:
    aid = uuid.UUID(str(account_id)) if account_id is not None else None
    stmt = select(ProxyPool).where(ProxyPool.name == name)
    stmt = stmt.where(
        ProxyPool.account_id == aid if aid is not None else ProxyPool.account_id.is_(None)
    )
    existing = await db.execute(stmt)
    if existing.scalar_one_or_none() is not None:
        raise DuplicatePoolNameError(f"Pool name already in use: {name}")
    pool = ProxyPool(name=name, description=description, account_id=aid)
    db.add(pool)
    await db.commit()
    await db.refresh(pool)
    return pool


async def list_pools(
    db: AsyncSession, account_id=_ANY_ACCOUNT
) -> list[tuple[ProxyPool, int]]:
    stmt = select(ProxyPool).order_by(ProxyPool.name)
    clause = _account_filter(ProxyPool.account_id, account_id)
    if clause is not None:
        stmt = stmt.where(clause)
    result = await db.execute(stmt)
    pools = list(result.scalars().all())
    counts = await db.execute(
        select(Proxy.pool_id, func.count())
        .where(Proxy.pool_id.is_not(None))
        .group_by(Proxy.pool_id)
    )
    count_map = {row[0]: row[1] for row in counts.fetchall()}
    return [(p, count_map.get(p.id, 0)) for p in pools]


async def get_pool(db: AsyncSession, pool_id: str) -> ProxyPool:
    result = await db.execute(
        select(ProxyPool).where(ProxyPool.id == uuid.UUID(str(pool_id)))
    )
    pool = result.scalar_one_or_none()
    if pool is None:
        raise ProxyPoolNotFoundError(f"Pool not found: {pool_id}")
    return pool


async def get_owned_pool(
    db: AsyncSession, pool_id: str, account_id
) -> ProxyPool:
    """Pool que pertence à conta indicada — usado no autosserviço do cliente.
    Trata "não é seu" como "não existe" para não vazar pools de terceiros."""
    pool = await get_pool(db, pool_id)
    if pool.account_id != uuid.UUID(str(account_id)):
        raise ProxyPoolNotFoundError(f"Pool not found: {pool_id}")
    return pool


async def delete_pool(db: AsyncSession, pool_id: str) -> None:
    pool = await get_pool(db, pool_id)
    await db.delete(pool)
    await db.commit()


# --------------------------------------------------------------------- proxies
async def create_proxy(db: AsyncSession, data, account_id=None) -> Proxy:
    if data.pool_id is not None:
        await get_pool(db, str(data.pool_id))
    proxy = Proxy(
        account_id=uuid.UUID(str(account_id)) if account_id is not None else None,
        pool_id=data.pool_id,
        name=data.name,
        provider=data.provider,
        ownership=data.ownership.value,
        type=data.type.value,
        scheme=data.scheme.value,
        host=data.host,
        port=data.port,
        username_encrypted=encrypt_value(data.username) if data.username else None,
        password_encrypted=encrypt_value(data.password) if data.password else None,
        rotation=data.rotation.value,
        session_ttl_s=data.session_ttl_s,
        priority=data.priority,
    )
    db.add(proxy)
    await db.commit()
    await db.refresh(proxy)
    return proxy


async def list_proxies(
    db: AsyncSession, pool_id: str | None = None, account_id=_ANY_ACCOUNT
) -> list[Proxy]:
    stmt = select(Proxy).order_by(Proxy.priority, Proxy.name)
    if pool_id is not None:
        stmt = stmt.where(Proxy.pool_id == uuid.UUID(str(pool_id)))
    clause = _account_filter(Proxy.account_id, account_id)
    if clause is not None:
        stmt = stmt.where(clause)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_proxy(db: AsyncSession, proxy_id: str) -> Proxy:
    result = await db.execute(
        select(Proxy).where(Proxy.id == uuid.UUID(str(proxy_id)))
    )
    proxy = result.scalar_one_or_none()
    if proxy is None:
        raise ProxyNotFoundError(f"Proxy not found: {proxy_id}")
    return proxy


async def get_owned_proxy(db: AsyncSession, proxy_id: str, account_id) -> Proxy:
    """Proxy que pertence à conta indicada — autosserviço do cliente."""
    proxy = await get_proxy(db, proxy_id)
    if proxy.account_id != uuid.UUID(str(account_id)):
        raise ProxyNotFoundError(f"Proxy not found: {proxy_id}")
    return proxy


async def update_proxy(db: AsyncSession, proxy_id: str, data) -> Proxy:
    proxy = await get_proxy(db, proxy_id)
    if data.pool_id is not None:
        await get_pool(db, str(data.pool_id))

    simple = {
        "name": data.name,
        "host": data.host,
        "port": data.port,
        "provider": data.provider,
        "session_ttl_s": data.session_ttl_s,
        "priority": data.priority,
        "pool_id": data.pool_id,
    }
    for field, value in simple.items():
        if value is not None:
            setattr(proxy, field, value)

    for field in ("scheme", "type", "ownership", "rotation", "status"):
        value = getattr(data, field)
        if value is not None:
            setattr(proxy, field, value.value)

    if data.username is not None:
        proxy.username_encrypted = encrypt_value(data.username)
    if data.password is not None:
        proxy.password_encrypted = encrypt_value(data.password)

    # Reativar manualmente limpa o último erro.
    if data.status is not None and data.status == ProxyStatus.ACTIVE:
        proxy.last_error = None
        proxy.last_error_at = None

    await db.commit()
    await db.refresh(proxy)
    return proxy


async def delete_proxy(db: AsyncSession, proxy_id: str) -> None:
    proxy = await get_proxy(db, proxy_id)
    await db.delete(proxy)
    await db.commit()


# --------------------------------------------------------- atribuição à API
async def assign_pool_to_api(
    db: AsyncSession, api_id: str, pool_id: str | None
) -> ExternalAPI:
    api = await get_api_by_id(db, api_id)
    if pool_id is not None:
        await get_pool(db, str(pool_id))
        api.proxy_pool_id = uuid.UUID(str(pool_id))
    else:
        api.proxy_pool_id = None
    await db.commit()
    await db.refresh(api)
    return api


# ----------------------------------------------- override por cliente (híbrido)
async def resolve_pool_id_for_client(
    db: AsyncSession, api: ExternalAPI, client_id=None
) -> uuid.UUID | None:
    """Pool efetivo na chamada de um cliente: o override do cliente para esta API
    quando existe, senão o default da API. É o coração da resolução híbrida."""
    if client_id is not None:
        result = await db.execute(
            select(ApiClientProxyPool.pool_id).where(
                ApiClientProxyPool.api_id == api.id,
                ApiClientProxyPool.account_id == uuid.UUID(str(client_id)),
            )
        )
        override = result.scalar_one_or_none()
        if override is not None:
            return override
    return api.proxy_pool_id


async def set_client_override(
    db: AsyncSession, api_id: str, account_id, pool_id: str | None
) -> uuid.UUID | None:
    """Define (ou limpa, com ``pool_id=None``) o pool que o cliente usa para a
    API. O pool precisa pertencer ao próprio cliente."""
    api = await get_api_by_id(db, api_id)
    aid = uuid.UUID(str(account_id))
    result = await db.execute(
        select(ApiClientProxyPool).where(
            ApiClientProxyPool.api_id == api.id,
            ApiClientProxyPool.account_id == aid,
        )
    )
    row = result.scalar_one_or_none()

    if pool_id is None:
        if row is not None:
            await db.delete(row)
            await db.commit()
        return None

    pool = await get_owned_pool(db, str(pool_id), aid)
    if row is None:
        row = ApiClientProxyPool(api_id=api.id, account_id=aid, pool_id=pool.id)
        db.add(row)
    else:
        row.pool_id = pool.id
    await db.commit()
    return pool.id


async def get_client_overrides(
    db: AsyncSession, account_id
) -> dict[uuid.UUID, uuid.UUID]:
    """Mapa api_id → pool_id dos overrides do cliente (para montar a tela)."""
    result = await db.execute(
        select(ApiClientProxyPool.api_id, ApiClientProxyPool.pool_id).where(
            ApiClientProxyPool.account_id == uuid.UUID(str(account_id))
        )
    )
    return {row.api_id: row.pool_id for row in result.fetchall()}


# ------------------------------------------------------- config para a SDK
async def get_pool_config_for_api(
    db: AsyncSession, api: ExternalAPI, client_id=None
) -> ProxyConfigResponse:
    """Proxies ativos do pool da API, com credenciais descriptografadas,
    ordenados por prioridade (menor = tentado primeiro). Resolve o pool de forma
    híbrida: override do cliente (``client_id``) quando existe, senão o da API."""
    pool_id = await resolve_pool_id_for_client(db, api, client_id)
    if pool_id is None:
        return ProxyConfigResponse(pool_id=None, pool_name=None, proxies=[])

    pool = await get_pool(db, str(pool_id))
    result = await db.execute(
        select(Proxy)
        .where(
            Proxy.pool_id == pool_id,
            Proxy.status == ProxyStatus.ACTIVE.value,
        )
        .order_by(Proxy.priority, Proxy.name)
    )
    proxies = list(result.scalars().all())
    items = [
        ProxyConfigItem(
            id=p.id,
            name=p.name,
            scheme=p.scheme,
            host=p.host,
            port=p.port,
            username=decrypt_value(p.username_encrypted)
            if p.username_encrypted
            else None,
            password=decrypt_value(p.password_encrypted)
            if p.password_encrypted
            else None,
            rotation=p.rotation,
            session_ttl_s=p.session_ttl_s,
            priority=p.priority,
        )
        for p in proxies
    ]
    return ProxyConfigResponse(pool_id=pool.id, pool_name=pool.name, proxies=items)


# --------------------------------------------------- report de falha da SDK
async def report_proxy_failure(
    db: AsyncSession, api: ExternalAPI, data, client_id=None
) -> Proxy:
    """Marca um proxy como failing/inactive. O proxy precisa pertencer ao pool
    efetivo daquela chamada (resolvido de forma híbrida) — uma API/cliente não
    mexe em proxy de outro."""
    pool_id = await resolve_pool_id_for_client(db, api, client_id)
    proxy = await get_proxy(db, str(data.proxy_id))
    if proxy.pool_id is None or proxy.pool_id != pool_id:
        raise ProxyNotFoundError("Proxy not in this API's pool")

    proxy.status = data.status.value
    proxy.last_error = data.message or data.error_code
    proxy.last_error_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(proxy)
    return proxy
