"""Autosserviço de proxies do cliente (dashboard).

Espelha o router admin, mas tudo é escopado à conta do usuário logado e liberado
pela capability ``Feature.PROXIES``. O cliente gerencia seus próprios pools e
proxies e escolhe, por API, qual pool seu a Bridge deve usar nas chamadas dele
(override da resolução híbrida). O admin continua vendo/gerenciando tudo no
router admin (`/proxies/*`).
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import Feature
from app.core.database import get_db
from app.domains.apis.service import APINotFoundError
from app.domains.auth.router import require_feature
from app.domains.auth.schemas import MeResponse
from app.domains.permissions.service import get_account_authorized_apis
from app.domains.proxies.models import ProxyOwnership
from app.domains.proxies.schemas import (
    APIPoolAssignRequest,
    ClientAssignmentItem,
    ClientAssignmentListResponse,
    ProxyCreate,
    ProxyListResponse,
    ProxyPoolCreate,
    ProxyPoolListResponse,
    ProxyPoolResponse,
    ProxyResponse,
    ProxyUpdate,
)
from app.domains.proxies.service import (
    DuplicatePoolNameError,
    ProxyNotFoundError,
    ProxyPoolNotFoundError,
    create_pool,
    create_proxy,
    delete_pool,
    get_client_overrides,
    get_owned_pool,
    get_owned_proxy,
    list_pools,
    list_proxies,
    set_client_override,
    to_response,
    update_proxy,
)

router = APIRouter(prefix="/client/proxies", tags=["proxies-client"])

_require = require_feature(Feature.PROXIES)


# ----------------------------------------------------------------------- pools
@router.post("/pools", response_model=ProxyPoolResponse, status_code=status.HTTP_201_CREATED)
async def create_pool_route(
    body: ProxyPoolCreate,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(_require),
) -> ProxyPoolResponse:
    try:
        pool = await create_pool(
            db, body.name, body.description, account_id=identity.account_id
        )
    except DuplicatePoolNameError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pool name already in use")
    return ProxyPoolResponse(
        id=pool.id, account_id=pool.account_id, name=pool.name,
        description=pool.description, proxy_count=0, created_at=pool.created_at,
    )


@router.get("/pools", response_model=ProxyPoolListResponse)
async def list_pools_route(
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(_require),
) -> ProxyPoolListResponse:
    pools = await list_pools(db, account_id=identity.account_id)
    items = [
        ProxyPoolResponse(
            id=p.id, account_id=p.account_id, name=p.name,
            description=p.description, proxy_count=count, created_at=p.created_at,
        )
        for p, count in pools
    ]
    return ProxyPoolListResponse(items=items, total=len(items))


@router.delete("/pools/{pool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pool_route(
    pool_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(_require),
) -> None:
    try:
        await get_owned_pool(db, str(pool_id), identity.account_id)
        await delete_pool(db, str(pool_id))
    except ProxyPoolNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pool not found")


# --------------------------------------------------------------------- proxies
@router.post("", response_model=ProxyResponse, status_code=status.HTTP_201_CREATED)
async def create_proxy_route(
    body: ProxyCreate,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(_require),
) -> ProxyResponse:
    if body.pool_id is not None:
        try:
            await get_owned_pool(db, str(body.pool_id), identity.account_id)
        except ProxyPoolNotFoundError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pool not found")
    body.ownership = ProxyOwnership.CLIENT  # proxy criado pelo cliente é dele
    proxy = await create_proxy(db, body, account_id=identity.account_id)
    return to_response(proxy)


@router.get("", response_model=ProxyListResponse)
async def list_proxies_route(
    pool_id: Optional[uuid.UUID] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(_require),
) -> ProxyListResponse:
    proxies = await list_proxies(
        db, str(pool_id) if pool_id else None, account_id=identity.account_id
    )
    items = [to_response(p) for p in proxies]
    return ProxyListResponse(items=items, total=len(items))


@router.patch("/{proxy_id}", response_model=ProxyResponse)
async def update_proxy_route(
    proxy_id: uuid.UUID,
    body: ProxyUpdate,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(_require),
) -> ProxyResponse:
    try:
        await get_owned_proxy(db, str(proxy_id), identity.account_id)
        if body.pool_id is not None:
            await get_owned_pool(db, str(body.pool_id), identity.account_id)
        proxy = await update_proxy(db, str(proxy_id), body)
    except ProxyNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy not found")
    except ProxyPoolNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pool not found")
    return to_response(proxy)


@router.delete("/{proxy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_proxy_route(
    proxy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(_require),
) -> None:
    try:
        proxy = await get_owned_proxy(db, str(proxy_id), identity.account_id)
    except ProxyNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy not found")
    await db.delete(proxy)
    await db.commit()


# ----------------------------------------- override do cliente: API → pool dele
@router.get("/assignments", response_model=ClientAssignmentListResponse)
async def list_assignments_route(
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(_require),
) -> ClientAssignmentListResponse:
    """APIs que a conta pode consumir + o pool que ela escolheu para cada uma."""
    apis = await get_account_authorized_apis(db, uuid.UUID(str(identity.account_id)))
    overrides = await get_client_overrides(db, identity.account_id)
    items = [
        ClientAssignmentItem(
            api_id=api.id, api_name=api.name, proxy_pool_id=overrides.get(api.id)
        )
        for api in apis
    ]
    return ClientAssignmentListResponse(items=items)


@router.put("/assignments/{api_id}", status_code=status.HTTP_200_OK)
async def set_assignment_route(
    api_id: uuid.UUID,
    body: APIPoolAssignRequest,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(_require),
) -> dict:
    try:
        pool_id = await set_client_override(
            db,
            str(api_id),
            identity.account_id,
            str(body.proxy_pool_id) if body.proxy_pool_id else None,
        )
    except APINotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API not found")
    except ProxyPoolNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pool not found")
    return {
        "api_id": str(api_id),
        "proxy_pool_id": str(pool_id) if pool_id else None,
    }
