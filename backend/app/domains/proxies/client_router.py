"""Autosserviço de proxies do cliente, por API.

O cliente só gerencia proxies de uma API quando o admin habilitou
``proxy_managed_by_client`` na permissão dele para aquela API (e ele tem a
capability ``Feature.PROXIES``). Tudo é escopado à conta: ele só vê/mexe nos
proxies dele (``account_id`` = conta).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import Feature
from app.core.database import get_db
from app.domains.apis.service import APINotFoundError
from app.domains.auth.router import require_feature
from app.domains.auth.schemas import MeResponse
from app.domains.permissions.service import get_permission
from app.domains.proxies.models import ProxyOwnership
from app.domains.proxies.schemas import (
    ProxyCreate,
    ProxyListResponse,
    ProxyResponse,
    ProxyUpdate,
)
from app.domains.proxies.service import (
    ProxyNotFoundError,
    create_proxy,
    delete_proxy,
    get_scoped_proxy,
    list_api_proxies,
    to_response,
    update_proxy,
)

router = APIRouter(prefix="/client/apis", tags=["proxies-client"])

_require = require_feature(Feature.PROXIES)


async def _ensure_managed(db: AsyncSession, identity: MeResponse, api_id: uuid.UUID):
    """Garante que o cliente pode gerenciar proxy desta API (permissão ativa com
    ``proxy_managed_by_client``)."""
    perm = await get_permission(db, str(identity.account_id), str(api_id))
    if perm is None or not perm.proxy_managed_by_client:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Proxy management not enabled for this API",
        )


@router.get("/{api_id}/proxies", response_model=ProxyListResponse)
async def list_route(
    api_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(_require),
) -> ProxyListResponse:
    await _ensure_managed(db, identity, api_id)
    proxies = await list_api_proxies(db, str(api_id), account_id=identity.account_id)
    items = [to_response(p) for p in proxies]
    return ProxyListResponse(items=items, total=len(items))


@router.post(
    "/{api_id}/proxies", response_model=ProxyResponse, status_code=status.HTTP_201_CREATED
)
async def create_route(
    api_id: uuid.UUID,
    body: ProxyCreate,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(_require),
) -> ProxyResponse:
    await _ensure_managed(db, identity, api_id)
    body.ownership = ProxyOwnership.CLIENT
    try:
        proxy = await create_proxy(
            db, str(api_id), body, account_id=identity.account_id
        )
    except APINotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API not found")
    return to_response(proxy)


@router.patch("/{api_id}/proxies/{proxy_id}", response_model=ProxyResponse)
async def update_route(
    api_id: uuid.UUID,
    proxy_id: uuid.UUID,
    body: ProxyUpdate,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(_require),
) -> ProxyResponse:
    await _ensure_managed(db, identity, api_id)
    try:
        proxy = await get_scoped_proxy(
            db, str(proxy_id), str(api_id), account_id=identity.account_id
        )
        proxy = await update_proxy(db, proxy, body)
    except ProxyNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy not found")
    return to_response(proxy)


@router.delete(
    "/{api_id}/proxies/{proxy_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_route(
    api_id: uuid.UUID,
    proxy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(_require),
) -> None:
    await _ensure_managed(db, identity, api_id)
    try:
        proxy = await get_scoped_proxy(
            db, str(proxy_id), str(api_id), account_id=identity.account_id
        )
    except ProxyNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy not found")
    await delete_proxy(db, proxy)
