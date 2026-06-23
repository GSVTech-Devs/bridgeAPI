from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import Feature
from app.core.database import get_db
from app.domains.apis.schemas import APIResponse
from app.domains.auth.router import get_current_user, require_feature
from app.domains.auth.schemas import MeResponse
from app.domains.permissions.schemas import (
    CatalogResponse,
    PermissionConfigRequest,
    PermissionCreateRequest,
    PermissionListResponse,
    PermissionResponse,
)
from app.domains.permissions.service import (
    DuplicatePermissionError,
    PermissionNotFoundError,
    get_account_authorized_apis,
    grant_permission,
    list_permissions,
    revoke_permission,
    set_permission_management,
)

router = APIRouter(tags=["permissions"])


@router.get("/permissions", response_model=PermissionListResponse)
async def get_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: MeResponse = Depends(get_current_user),
) -> PermissionListResponse:
    items = await list_permissions(db)
    return PermissionListResponse(items=items, total=len(items))


@router.post(
    "/permissions",
    response_model=PermissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def grant(
    body: PermissionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: MeResponse = Depends(get_current_user),
) -> PermissionResponse:
    try:
        permission = await grant_permission(
            db,
            str(body.account_id),
            str(body.api_id),
            proxy_managed_by_client=body.proxy_managed_by_client,
            captcha_managed_by_client=body.captcha_managed_by_client,
        )
    except DuplicatePermissionError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Permission already exists for this account and API",
        )
    return PermissionResponse.model_validate(permission)


@router.patch(
    "/permissions/{account_id}/{api_id}/revoke",
    response_model=PermissionResponse,
)
async def revoke(
    account_id: uuid.UUID,
    api_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: MeResponse = Depends(get_current_user),
) -> PermissionResponse:
    try:
        permission = await revoke_permission(db, str(account_id), str(api_id))
    except PermissionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active permission not found",
        )
    return PermissionResponse.model_validate(permission)


@router.patch(
    "/permissions/{account_id}/{api_id}/config",
    response_model=PermissionResponse,
)
async def configure(
    account_id: uuid.UUID,
    api_id: uuid.UUID,
    body: PermissionConfigRequest,
    db: AsyncSession = Depends(get_db),
    current_user: MeResponse = Depends(get_current_user),
) -> PermissionResponse:
    """Liga/desliga o autosserviço de proxy/captcha do cliente para esta API."""
    try:
        permission = await set_permission_management(
            db,
            str(account_id),
            str(api_id),
            proxy_managed_by_client=body.proxy_managed_by_client,
            captcha_managed_by_client=body.captcha_managed_by_client,
        )
    except PermissionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active permission not found",
        )
    return PermissionResponse.model_validate(permission)


@router.get("/catalog", response_model=CatalogResponse)
async def catalog(
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(require_feature(Feature.CATALOG)),
) -> CatalogResponse:
    apis = await get_account_authorized_apis(db, identity.account_id)
    items = [APIResponse.model_validate(api).model_dump() for api in apis]
    return CatalogResponse(items=items, total=len(items))
