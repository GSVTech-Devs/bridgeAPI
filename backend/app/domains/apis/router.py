from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.apis.schemas import (
    APICreateRequest,
    APIDetailResponse,
    APIListResponse,
    APIResponse,
    EndpointCreateRequest,
    EndpointResponse,
)
from app.domains.apis.service import (
    APINotFoundError,
    DuplicateAPINameError,
    add_endpoint,
    disable_api,
    enable_api,
    get_api_by_id,
    list_apis,
    list_endpoints_for_api,
    register_api,
)
from app.domains.auth.router import get_current_user
from app.domains.auth.schemas import MeResponse

router = APIRouter(prefix="/apis", tags=["apis"])


@router.post("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def create_api(
    body: APICreateRequest,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> APIResponse:
    try:
        api = await register_api(
            db,
            name=body.name,
            base_url=str(body.base_url),
            master_key=body.master_key,
            auth_type=body.auth_type,
            url_template=body.url_template,
        )
    except DuplicateAPINameError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="API name already registered",
        )
    return APIResponse.model_validate(api)


@router.get("", response_model=APIListResponse)
async def list_all(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> APIListResponse:
    apis, total = await list_apis(db, page, per_page)
    return APIListResponse(
        items=[APIResponse.model_validate(a) for a in apis],
        total=total,
    )


@router.get("/{api_id}", response_model=APIDetailResponse)
async def get_api(
    api_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> APIDetailResponse:
    try:
        api = await get_api_by_id(db, str(api_id))
    except APINotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API not found"
        )
    endpoints = await list_endpoints_for_api(db, api_id)
    return APIDetailResponse(
        id=api.id,
        name=api.name,
        base_url=api.base_url,
        auth_type=api.auth_type,
        status=api.status,
        created_at=api.created_at,
        endpoints=[EndpointResponse.model_validate(e) for e in endpoints],
    )


@router.post(
    "/{api_id}/endpoints",
    response_model=EndpointResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_endpoint(
    api_id: uuid.UUID,
    body: EndpointCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> EndpointResponse:
    try:
        endpoint = await add_endpoint(
            db,
            api_id=str(api_id),
            method=body.method,
            path=body.path,
            cost_rule=body.cost_rule,
        )
    except APINotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API not found"
        )
    return EndpointResponse.model_validate(endpoint)


@router.patch("/{api_id}/disable", response_model=APIResponse)
async def disable(
    api_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> APIResponse:
    try:
        api = await disable_api(db, str(api_id))
    except APINotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API not found"
        )
    return APIResponse.model_validate(api)


@router.patch("/{api_id}/enable", response_model=APIResponse)
async def enable(
    api_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> APIResponse:
    try:
        api = await enable_api(db, str(api_id))
    except APINotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API not found"
        )
    return APIResponse.model_validate(api)
