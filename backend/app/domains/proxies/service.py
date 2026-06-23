from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_value, encrypt_value
from app.domains.apis.models import ExternalAPI
from app.domains.apis.service import get_api_by_id
from app.domains.permissions.service import get_permission
from app.domains.proxies.models import Proxy, ProxyOwnership, ProxyStatus
from app.domains.proxies.schemas import (
    ProxyConfigItem,
    ProxyConfigResponse,
    ProxyMonitorItem,
    ProxyResponse,
)

# Sentinela para "sem filtro de dono" (monitoramento vê tudo) vs. account_id=None
# (só os do admin) vs. um UUID (de um cliente).
_ANY_ACCOUNT = object()


class ProxyNotFoundError(Exception):
    pass


# --------------------------------------------------------------------- helpers
def to_response(proxy: Proxy) -> ProxyResponse:
    return ProxyResponse(
        id=proxy.id,
        api_id=proxy.api_id,
        account_id=proxy.account_id,
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


def _account_clause(account_id):
    if account_id is _ANY_ACCOUNT:
        return None
    if account_id is None:
        return Proxy.account_id.is_(None)
    return Proxy.account_id == uuid.UUID(str(account_id))


# --------------------------------------------------------------------- CRUD
async def create_proxy(db: AsyncSession, api_id: str, data, account_id=None) -> Proxy:
    await get_api_by_id(db, api_id)  # valida a API (404 se não existe)
    proxy = Proxy(
        api_id=uuid.UUID(str(api_id)),
        account_id=uuid.UUID(str(account_id)) if account_id is not None else None,
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


async def list_api_proxies(
    db: AsyncSession, api_id: str, account_id=_ANY_ACCOUNT
) -> list[Proxy]:
    stmt = (
        select(Proxy)
        .where(Proxy.api_id == uuid.UUID(str(api_id)))
        .order_by(Proxy.priority, Proxy.name)
    )
    clause = _account_clause(account_id)
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


async def get_scoped_proxy(
    db: AsyncSession, proxy_id: str, api_id: str, account_id=_ANY_ACCOUNT
) -> Proxy:
    """Proxy que pertence à API (e, se filtrado, ao dono). Trata "não é seu"
    como "não existe" para não vazar proxies de terceiros."""
    proxy = await get_proxy(db, proxy_id)
    if proxy.api_id != uuid.UUID(str(api_id)):
        raise ProxyNotFoundError(f"Proxy not found: {proxy_id}")
    if account_id is not _ANY_ACCOUNT:
        want = uuid.UUID(str(account_id)) if account_id is not None else None
        if proxy.account_id != want:
            raise ProxyNotFoundError(f"Proxy not found: {proxy_id}")
    return proxy


async def update_proxy(db: AsyncSession, proxy: Proxy, data) -> Proxy:
    simple = {
        "name": data.name,
        "host": data.host,
        "port": data.port,
        "provider": data.provider,
        "session_ttl_s": data.session_ttl_s,
        "priority": data.priority,
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


async def delete_proxy(db: AsyncSession, proxy: Proxy) -> None:
    await db.delete(proxy)
    await db.commit()


# --------------------------------------------------- resolução p/ a SDK
async def resolve_owner_for_request(db: AsyncSession, api: ExternalAPI, client_id=None):
    """Dono dos proxies a usar na chamada: o cliente (se a permissão dele para
    esta API marca ``proxy_managed_by_client``) — senão o admin (None)."""
    if client_id is None:
        return None
    perm = await get_permission(db, str(client_id), str(api.id))
    if perm is not None and perm.proxy_managed_by_client:
        return uuid.UUID(str(client_id))
    return None


async def _active_proxies(db: AsyncSession, api_id, owner) -> list[Proxy]:
    clause = Proxy.account_id.is_(None) if owner is None else Proxy.account_id == owner
    result = await db.execute(
        select(Proxy)
        .where(Proxy.api_id == api_id, Proxy.status == ProxyStatus.ACTIVE.value, clause)
        .order_by(Proxy.priority, Proxy.name)
    )
    return list(result.scalars().all())


async def get_proxy_config_for_api(
    db: AsyncSession, api: ExternalAPI, client_id=None
) -> ProxyConfigResponse:
    """Proxies ativos a usar nesta chamada (resolvidos por dono), com credenciais
    descriptografadas, por prioridade. Vazio se a API não usa proxy."""
    if not api.uses_proxy:
        return ProxyConfigResponse(proxies=[])
    owner = await resolve_owner_for_request(db, api, client_id)
    proxies = await _active_proxies(db, api.id, owner)
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
    return ProxyConfigResponse(proxies=items)


async def report_proxy_failure(
    db: AsyncSession, api: ExternalAPI, data, client_id=None
) -> Proxy:
    """Marca um proxy como failing/inactive. O proxy precisa ser desta API e do
    dono resolvido para a chamada (cliente ou admin)."""
    owner = await resolve_owner_for_request(db, api, client_id)
    proxy = await get_proxy(db, str(data.proxy_id))
    if proxy.api_id != api.id or proxy.account_id != owner:
        raise ProxyNotFoundError("Proxy not in this API/owner scope")

    proxy.status = data.status.value
    proxy.last_error = data.message or data.error_code
    proxy.last_error_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(proxy)
    return proxy


# ------------------------------------------------------ monitoramento agregado
async def monitor_proxies(db: AsyncSession) -> list[ProxyMonitorItem]:
    """Todos os proxies de todas as APIs, com nome da API — visão de monitoramento."""
    result = await db.execute(
        select(Proxy, ExternalAPI.name)
        .join(ExternalAPI, ExternalAPI.id == Proxy.api_id)
        .order_by(ExternalAPI.name, Proxy.priority, Proxy.name)
    )
    return [
        ProxyMonitorItem(
            id=p.id,
            api_id=p.api_id,
            api_name=api_name,
            account_id=p.account_id,
            name=p.name,
            host=p.host,
            port=p.port,
            status=p.status,
            priority=p.priority,
            last_error=p.last_error,
            last_error_at=p.last_error_at,
        )
        for p, api_name in result.all()
    ]
