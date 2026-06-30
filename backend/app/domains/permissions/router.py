from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import Feature
from app.core.database import get_db
from app.domains.apis.schemas import (
    APIResponse,
    UserDocResponse,
    build_user_doc_operation,
)
from app.domains.apis.service import (
    APINotFoundError,
    api_ids_with_visible_docs,
    get_api_by_id,
    list_doc_operations,
)
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
    get_permission,
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
    docs_ids = await api_ids_with_visible_docs(db, [api.id for api in apis])
    items = []
    for api in apis:
        item = APIResponse.model_validate(api).model_dump()
        # Tem doc se há operações visíveis OU uma visão geral personalizada.
        item["has_docs"] = api.id in docs_ids or bool(api.custom_docs_md)
        items.append(item)
    return CatalogResponse(items=items, total=len(items))


@router.get("/catalog/{api_id}/docs", response_model=UserDocResponse)
async def catalog_api_docs(
    api_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(require_feature(Feature.DOCS)),
) -> UserDocResponse:
    """Documentação do cliente para uma API autorizada (só operações visíveis).

    Gating: a conta precisa de permissão ativa para a API; sem ela responde 404
    (não revela a existência da API)."""
    permission = await get_permission(db, str(identity.account_id), str(api_id))
    if permission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API not found"
        )
    try:
        api = await get_api_by_id(db, str(api_id))
    except APINotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API not found"
        )
    rows = await list_doc_operations(db, api.id, only_visible=True)
    return UserDocResponse(
        api_id=api.id,
        api_name=api.name,
        slug=api.slug,
        base_url=api.base_url,
        custom_docs_md=api.custom_docs_md,
        operations=[build_user_doc_operation(r) for r in rows],
    )
