from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.apis.openapi import InvalidSpecError, fetch_spec
from app.domains.apis.schemas import (
    APICreateRequest,
    APIDetailResponse,
    APIListResponse,
    APIResponse,
    APIUpdateRequest,
    BulkImportRequest,
    BulkImportResponse,
    DocOperationListResponse,
    DocOperationResponse,
    DocOperationVisibilityRequest,
    DocSyncResponse,
    EndpointCreateRequest,
    EndpointResponse,
    ImportedOperation,
    OpenAPIImportRequest,
    OpenAPIImportResponse,
    build_doc_operation_response,
)
from app.domains.apis.service import (
    APINotFoundError,
    DocOperationNotFoundError,
    DocsNotConfiguredError,
    DuplicateAPINameError,
    DuplicateSlugError,
    add_endpoint,
    bulk_register_apis,
    delete_api,
    disable_api,
    enable_api,
    get_api_by_id,
    list_apis,
    list_doc_operations,
    list_endpoints_for_api,
    register_api,
    set_doc_operation_visibility,
    sync_doc_operations,
    update_api,
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
            slug=body.slug,
            base_url=str(body.base_url),
            master_key=body.master_key,
            auth_type=body.auth_type,
            url_template=body.url_template,
            cost_per_query=body.cost_per_query,
            uses_proxy=body.uses_proxy,
            uses_captcha=body.uses_captcha,
            request_method=body.request_method,
            request_body_template=body.request_body_template,
            openapi_url=body.openapi_url,
            custom_docs_md=body.custom_docs_md,
        )
    except DuplicateAPINameError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="API name already registered",
        )
    except DuplicateSlugError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slug already in use",
        )
    return APIResponse.model_validate(api)


@router.post("/import", response_model=OpenAPIImportResponse)
async def import_openapi(
    body: OpenAPIImportRequest,
    _: MeResponse = Depends(get_current_user),
) -> OpenAPIImportResponse:
    """Busca o OpenAPI/Swagger na URL da doc e devolve, por operação, o método e
    um body template — para o admin revisar e importar em massa (ver /import/bulk)."""
    try:
        parsed = await fetch_spec(body.url)
    except InvalidSpecError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return OpenAPIImportResponse(
        title=parsed["title"],
        base_url=parsed["base_url"],
        operations=[ImportedOperation(**op) for op in parsed["operations"]],
    )


@router.post("/import/bulk", response_model=BulkImportResponse)
async def import_bulk(
    body: BulkImportRequest,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> BulkImportResponse:
    """Cria as APIs selecionadas do import como rascunho (``inactive``).

    Cada item vem pré-configurado da tela de import; o admin ativa e termina de
    configurar (proxy/captcha/custo) depois, na tela de edição de cada uma."""
    results = await bulk_register_apis(db, [item.model_dump() for item in body.items])
    created = sum(1 for r in results if r["status"] == "created")
    skipped = len(results) - created
    return BulkImportResponse(created=created, skipped=skipped, results=results)


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
        slug=api.slug,
        base_url=api.base_url,
        url_template=api.url_template,
        request_method=api.request_method,
        request_body_template=api.request_body_template,
        auth_type=api.auth_type,
        status=api.status,
        cost_per_query=api.cost_per_query,
        uses_proxy=api.uses_proxy,
        uses_captcha=api.uses_captcha,
        openapi_url=api.openapi_url,
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


@router.patch("/{api_id}", response_model=APIResponse)
async def update(
    api_id: uuid.UUID,
    body: APIUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> APIResponse:
    try:
        api = await update_api(
            db,
            str(api_id),
            name=body.name,
            slug=body.slug,
            base_url=str(body.base_url) if body.base_url else None,
            url_template=body.url_template,
            master_key=body.master_key,
            auth_type=body.auth_type,
            cost_per_query=body.cost_per_query,
            uses_proxy=body.uses_proxy,
            uses_captcha=body.uses_captcha,
            request_method=body.request_method,
            request_body_template=body.request_body_template,
            openapi_url=body.openapi_url,
            custom_docs_md=body.custom_docs_md,
        )
    except APINotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API not found"
        )
    except DuplicateAPINameError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="API name already registered"
        )
    except DuplicateSlugError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Slug already in use"
        )
    return APIResponse.model_validate(api)


@router.delete("/{api_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    api_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> None:
    try:
        await delete_api(db, str(api_id))
    except APINotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API not found"
        )


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


# ---------------------------------------------------------------------------
# Documentação do cliente (docs)  (admin)
# ---------------------------------------------------------------------------


@router.post("/{api_id}/docs/sync", response_model=DocSyncResponse)
async def sync_docs(
    api_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> DocSyncResponse:
    """Sincroniza a doc do cliente a partir do ``openapi_url`` da API.

    Faz upsert preservando os toggles de visibilidade já editados."""
    try:
        result = await sync_doc_operations(db, str(api_id))
    except APINotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API not found"
        )
    except DocsNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except InvalidSpecError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return DocSyncResponse(**result)


@router.get("/{api_id}/docs", response_model=DocOperationListResponse)
async def list_docs(
    api_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> DocOperationListResponse:
    rows = await list_doc_operations(db, api_id)
    items = [build_doc_operation_response(r) for r in rows]
    return DocOperationListResponse(items=items, total=len(items))


@router.patch("/{api_id}/docs/{op_id}", response_model=DocOperationResponse)
async def set_doc_visibility(
    api_id: uuid.UUID,
    op_id: uuid.UUID,
    body: DocOperationVisibilityRequest,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> DocOperationResponse:
    try:
        row = await set_doc_operation_visibility(
            db, str(api_id), str(op_id), body.visible
        )
    except DocOperationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doc operation not found"
        )
    return build_doc_operation_response(row)
