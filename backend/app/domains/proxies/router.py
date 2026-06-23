from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.apis.service import APINotFoundError
from app.domains.auth.router import get_current_user
from app.domains.auth.schemas import MeResponse
from app.domains.proxies.schemas import (
    APIPoolAssignRequest,
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
    assign_pool_to_api,
    create_pool,
    create_proxy,
    delete_pool,
    delete_proxy,
    get_proxy,
    list_pools,
    list_proxies,
    to_response,
    update_proxy,
)

router = APIRouter(prefix="/proxies", tags=["proxies"])


# ----------------------------------------------------------------------- pools
@router.post("/pools", response_model=ProxyPoolResponse, status_code=status.HTTP_201_CREATED)
async def create_pool_route(
    body: ProxyPoolCreate,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> ProxyPoolResponse:
    try:
        pool = await create_pool(db, body.name, body.description)
    except DuplicatePoolNameError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pool name already in use")
    return ProxyPoolResponse(
        id=pool.id, name=pool.name, description=pool.description,
        proxy_count=0, created_at=pool.created_at,
    )


@router.get("/pools", response_model=ProxyPoolListResponse)
async def list_pools_route(
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> ProxyPoolListResponse:
    pools = await list_pools(db)
    items = [
        ProxyPoolResponse(
            id=p.id, name=p.name, description=p.description,
            proxy_count=count, created_at=p.created_at,
        )
        for p, count in pools
    ]
    return ProxyPoolListResponse(items=items, total=len(items))


@router.delete("/pools/{pool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pool_route(
    pool_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> None:
    try:
        await delete_pool(db, str(pool_id))
    except ProxyPoolNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pool not found")


# ----------------------------------------------------- atribuição pool ↔ API
@router.put("/assignments/{api_id}", status_code=status.HTTP_200_OK)
async def assign_pool_route(
    api_id: uuid.UUID,
    body: APIPoolAssignRequest,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> dict:
    try:
        api = await assign_pool_to_api(
            db, str(api_id), str(body.proxy_pool_id) if body.proxy_pool_id else None
        )
    except APINotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API not found")
    except ProxyPoolNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pool not found")
    return {
        "api_id": str(api.id),
        "proxy_pool_id": str(api.proxy_pool_id) if api.proxy_pool_id else None,
    }


# --------------------------------------------------------------------- proxies
@router.post("", response_model=ProxyResponse, status_code=status.HTTP_201_CREATED)
async def create_proxy_route(
    body: ProxyCreate,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> ProxyResponse:
    try:
        proxy = await create_proxy(db, body)
    except ProxyPoolNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pool not found")
    return to_response(proxy)


@router.get("", response_model=ProxyListResponse)
async def list_proxies_route(
    pool_id: Optional[uuid.UUID] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> ProxyListResponse:
    proxies = await list_proxies(db, str(pool_id) if pool_id else None)
    items = [to_response(p) for p in proxies]
    return ProxyListResponse(items=items, total=len(items))


@router.get("/{proxy_id}", response_model=ProxyResponse)
async def get_proxy_route(
    proxy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> ProxyResponse:
    try:
        proxy = await get_proxy(db, str(proxy_id))
    except ProxyNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy not found")
    return to_response(proxy)


@router.patch("/{proxy_id}", response_model=ProxyResponse)
async def update_proxy_route(
    proxy_id: uuid.UUID,
    body: ProxyUpdate,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> ProxyResponse:
    try:
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
    _: MeResponse = Depends(get_current_user),
) -> None:
    try:
        await delete_proxy(db, str(proxy_id))
    except ProxyNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy not found")
