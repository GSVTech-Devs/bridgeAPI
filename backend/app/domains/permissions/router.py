from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.apis.schemas import APIResponse
from app.domains.auth.router import get_current_client, get_current_user
from app.domains.auth.schemas import MeResponse
from app.domains.permissions.schemas import (
    CatalogResponse,
    PermissionCreateRequest,
    PermissionResponse,
)
from app.domains.permissions.service import (
    DuplicatePermissionError,
    PermissionNotFoundError,
    get_client_authorized_apis,
    grant_permission,
    revoke_permission,
)

router = APIRouter(tags=["permissions"])


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
        permission = await grant_permission(db, str(body.client_id), str(body.api_id))
    except DuplicatePermissionError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Permission already exists for this client and API",
        )
    return PermissionResponse.model_validate(permission)


@router.patch(
    "/permissions/{client_id}/{api_id}/revoke",
    response_model=PermissionResponse,
)
async def revoke(
    client_id: uuid.UUID,
    api_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: MeResponse = Depends(get_current_user),
) -> PermissionResponse:
    try:
        permission = await revoke_permission(db, str(client_id), str(api_id))
    except PermissionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active permission not found",
        )
    return PermissionResponse.model_validate(permission)


@router.get("/catalog", response_model=CatalogResponse)
async def catalog(
    db: AsyncSession = Depends(get_db),
    current_client: MeResponse = Depends(get_current_client),
) -> CatalogResponse:
    apis = await get_client_authorized_apis(db, current_client.email)
    items = [APIResponse.model_validate(api).model_dump() for api in apis]
    return CatalogResponse(items=items, total=len(items))
