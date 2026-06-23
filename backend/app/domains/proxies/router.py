from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.apis.service import APINotFoundError
from app.domains.auth.router import get_current_user
from app.domains.auth.schemas import MeResponse
from app.domains.proxies.schemas import (
    ProxyCreate,
    ProxyListResponse,
    ProxyMonitorResponse,
    ProxyResponse,
    ProxyUpdate,
)
from app.domains.proxies.service import (
    ProxyNotFoundError,
    create_proxy,
    delete_proxy,
    get_scoped_proxy,
    list_api_proxies,
    monitor_proxies,
    to_response,
    update_proxy,
)

# Proxies do admin para uma API, aninhados no recurso da API. (O cliente usa o
# client_router; ambos manipulam linhas da mesma tabela, escopadas por dono.)
router = APIRouter(prefix="/apis", tags=["proxies"])


@router.get("/{api_id}/proxies", response_model=ProxyListResponse)
async def list_route(
    api_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> ProxyListResponse:
    # Admin gerencia os proxies da plataforma (account_id IS NULL).
    proxies = await list_api_proxies(db, str(api_id), account_id=None)
    items = [to_response(p) for p in proxies]
    return ProxyListResponse(items=items, total=len(items))


@router.post(
    "/{api_id}/proxies", response_model=ProxyResponse, status_code=status.HTTP_201_CREATED
)
async def create_route(
    api_id: uuid.UUID,
    body: ProxyCreate,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> ProxyResponse:
    try:
        proxy = await create_proxy(db, str(api_id), body, account_id=None)
    except APINotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API not found")
    return to_response(proxy)


@router.patch("/{api_id}/proxies/{proxy_id}", response_model=ProxyResponse)
async def update_route(
    api_id: uuid.UUID,
    proxy_id: uuid.UUID,
    body: ProxyUpdate,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> ProxyResponse:
    try:
        proxy = await get_scoped_proxy(db, str(proxy_id), str(api_id), account_id=None)
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
    _: MeResponse = Depends(get_current_user),
) -> None:
    try:
        proxy = await get_scoped_proxy(db, str(proxy_id), str(api_id), account_id=None)
    except ProxyNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy not found")
    await delete_proxy(db, proxy)


# ----------------------------------------------------------- monitoramento
monitor_router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@monitor_router.get("/proxies", response_model=ProxyMonitorResponse)
async def monitor_proxies_route(
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> ProxyMonitorResponse:
    items = await monitor_proxies(db)
    return ProxyMonitorResponse(items=items, total=len(items))
