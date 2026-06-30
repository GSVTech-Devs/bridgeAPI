from __future__ import annotations

import json
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_value, encrypt_value
from app.domains.apis.models import (
    APIAuthType,
    ApiDocOperation,
    APIStatus,
    Endpoint,
    ExternalAPI,
    HTTPMethod,
)
from app.domains.apis.openapi import fetch_spec_docs


class DuplicateAPINameError(Exception):
    pass


class APINotFoundError(Exception):
    pass


class DuplicateSlugError(Exception):
    pass


class DocsNotConfiguredError(Exception):
    """API sem ``openapi_url`` configurada para sincronizar a documentação."""


class DocOperationNotFoundError(Exception):
    pass


async def register_api(
    db: AsyncSession,
    name: str,
    base_url: str,
    master_key: str | None = None,
    auth_type: APIAuthType = APIAuthType.NONE,
    url_template: str | None = None,
    slug: str | None = None,
    cost_per_query: float | None = None,
    uses_proxy: bool = False,
    uses_captcha: bool = False,
    request_method: str | None = None,
    request_body_template: str | None = None,
    openapi_url: str | None = None,
    status: APIStatus = APIStatus.ACTIVE,
) -> ExternalAPI:
    existing = await db.execute(select(ExternalAPI).where(ExternalAPI.name == name))
    if existing.scalar_one_or_none() is not None:
        raise DuplicateAPINameError(f"API name already registered: {name}")

    if slug is not None:
        slug_conflict = await db.execute(
            select(ExternalAPI).where(ExternalAPI.slug == slug)
        )
        if slug_conflict.scalar_one_or_none() is not None:
            raise DuplicateSlugError(f"Slug already in use: {slug}")

    encrypted = encrypt_value(master_key) if master_key is not None else None
    api = ExternalAPI(
        name=name,
        slug=slug,
        base_url=base_url,
        url_template=url_template,
        master_key_encrypted=encrypted,
        auth_type=auth_type,
        cost_per_query=cost_per_query,
        uses_proxy=uses_proxy,
        uses_captcha=uses_captcha,
        request_method=request_method or None,
        request_body_template=request_body_template or None,
        openapi_url=openapi_url or None,
        status=status,
    )
    db.add(api)
    await db.commit()
    await db.refresh(api)
    return api


async def bulk_register_apis(db: AsyncSession, items: list[dict]) -> list[dict]:
    """Cria várias APIs como rascunho (``INACTIVE``), uma por item.

    Resiliente: itens com nome/slug duplicado ou base_url inválido são pulados
    com um motivo, sem abortar o lote. Devolve um resultado por item:
    ``{name, status: created|skipped, id?, reason?}``.
    """
    results: list[dict] = []
    for item in items:
        name = item.get("name") or ""
        base_url = (item.get("base_url") or "").strip()
        if not name or not base_url:
            results.append(
                {
                    "name": name,
                    "status": "skipped",
                    "reason": "nome ou base_url ausente",
                }
            )
            continue
        if not (base_url.startswith("http://") or base_url.startswith("https://")):
            results.append(
                {
                    "name": name,
                    "status": "skipped",
                    "reason": "base_url deve ser http(s)",
                }
            )
            continue
        auth_raw = item.get("auth_type") or "none"
        try:
            auth_type = APIAuthType(auth_raw)
        except ValueError:
            auth_type = APIAuthType.NONE
        try:
            api = await register_api(
                db,
                name=name,
                base_url=base_url,
                auth_type=auth_type,
                cost_per_query=item.get("cost_per_query"),
                uses_proxy=bool(item.get("uses_proxy", False)),
                uses_captcha=bool(item.get("uses_captcha", False)),
                request_method=item.get("request_method"),
                request_body_template=item.get("request_body_template"),
                status=APIStatus.INACTIVE,
            )
            results.append({"name": name, "status": "created", "id": str(api.id)})
        except (DuplicateAPINameError, DuplicateSlugError) as exc:
            results.append({"name": name, "status": "skipped", "reason": str(exc)})
    return results


async def list_apis(
    db: AsyncSession, page: int = 1, per_page: int = 20
) -> tuple[list[ExternalAPI], int]:
    total_result = await db.execute(select(func.count()).select_from(ExternalAPI))
    total = total_result.scalar_one()

    result = await db.execute(
        select(ExternalAPI).offset((page - 1) * per_page).limit(per_page)
    )
    return list(result.scalars().all()), total


async def get_api_by_id(db: AsyncSession, api_id: str) -> ExternalAPI:
    result = await db.execute(select(ExternalAPI).where(ExternalAPI.id == api_id))
    api = result.scalar_one_or_none()
    if api is None:
        raise APINotFoundError(f"API not found: {api_id}")
    return api


async def get_api_by_slug(db: AsyncSession, slug: str) -> ExternalAPI:
    result = await db.execute(select(ExternalAPI).where(ExternalAPI.slug == slug))
    api = result.scalar_one_or_none()
    if api is None:
        raise APINotFoundError(f"API not found: {slug}")
    return api


async def add_endpoint(
    db: AsyncSession,
    api_id: str,
    method: HTTPMethod,
    path: str,
    cost_rule: float | None = None,
) -> Endpoint:
    api = await get_api_by_id(db, api_id)
    endpoint = Endpoint(
        api_id=api.id,
        method=method,
        path=path,
        cost_rule=cost_rule,
    )
    db.add(endpoint)
    await db.commit()
    await db.refresh(endpoint)
    return endpoint


async def update_api(
    db: AsyncSession,
    api_id: str,
    name: str | None = None,
    slug: str | None = None,
    base_url: str | None = None,
    url_template: str | None = None,
    master_key: str | None = None,
    auth_type: APIAuthType | None = None,
    cost_per_query: float | None = None,
    uses_proxy: bool | None = None,
    uses_captcha: bool | None = None,
    request_method: str | None = None,
    request_body_template: str | None = None,
    openapi_url: str | None = None,
) -> ExternalAPI:
    api = await get_api_by_id(db, api_id)

    if name is not None and name != api.name:
        conflict = await db.execute(select(ExternalAPI).where(ExternalAPI.name == name))
        if conflict.scalar_one_or_none() is not None:
            raise DuplicateAPINameError(f"API name already registered: {name}")
        api.name = name

    if slug is not None and slug != api.slug:
        conflict = await db.execute(select(ExternalAPI).where(ExternalAPI.slug == slug))
        if conflict.scalar_one_or_none() is not None:
            raise DuplicateSlugError(f"Slug already in use: {slug}")
        api.slug = slug

    if base_url is not None:
        api.base_url = base_url
    if url_template is not None:
        api.url_template = url_template or None
    if auth_type is not None:
        api.auth_type = auth_type
    if cost_per_query is not None:
        api.cost_per_query = cost_per_query
    if uses_proxy is not None:
        api.uses_proxy = uses_proxy
    if uses_captcha is not None:
        api.uses_captcha = uses_captcha
    if request_method is not None:
        api.request_method = request_method or None  # "" limpa (repassa cliente)
    if request_body_template is not None:
        api.request_body_template = request_body_template or None
    if openapi_url is not None:
        api.openapi_url = openapi_url or None  # "" limpa
    if master_key:
        from app.core.security import encrypt_value

        api.master_key_encrypted = encrypt_value(master_key)

    await db.commit()
    await db.refresh(api)
    return api


async def disable_api(db: AsyncSession, api_id: str) -> ExternalAPI:
    api = await get_api_by_id(db, api_id)
    api.status = APIStatus.INACTIVE
    await db.commit()
    await db.refresh(api)
    return api


async def enable_api(db: AsyncSession, api_id: str) -> ExternalAPI:
    api = await get_api_by_id(db, api_id)
    api.status = APIStatus.ACTIVE
    await db.commit()
    await db.refresh(api)
    return api


async def delete_api(db: AsyncSession, api_id: str) -> None:
    api = await get_api_by_id(db, api_id)
    await db.delete(api)
    await db.commit()


async def list_endpoints_for_api(db: AsyncSession, api_id: object) -> list[Endpoint]:
    result = await db.execute(select(Endpoint).where(Endpoint.api_id == api_id))
    return list(result.scalars().all())


# --------------------------------------------- documentação do cliente (docs)
def _doc_payload(op: dict) -> str:
    """Serializa o que renderiza a doc (parâmetros, exemplo, respostas)."""
    return json.dumps(
        {
            "parameters": op.get("parameters", []),
            "request_example": op.get("request_example"),
            "responses": op.get("responses", []),
        },
        ensure_ascii=False,
    )


def _doc_fetch_auth_headers(api: ExternalAPI) -> dict:
    """Credencial para buscar o ``openapi.json`` protegido da API externa.

    Usa a mesma master key + ``auth_type`` do proxy (ver
    ``proxy.service.build_upstream_headers``). Vazio quando a API não tem master key.
    """
    if not api.master_key_encrypted:
        return {}
    key = decrypt_value(api.master_key_encrypted)
    if api.auth_type == APIAuthType.API_KEY:
        return {"x-api-key": key}
    if api.auth_type == APIAuthType.BEARER:
        return {"authorization": f"Bearer {key}"}
    if api.auth_type == APIAuthType.BASIC:
        return {"authorization": f"Basic {key}"}
    return {}


async def sync_doc_operations(db: AsyncSession, api_id: str) -> dict:
    """Sincroniza as operações da doc a partir do ``openapi_url`` da API.

    Faz upsert por (method, path) preservando o flag ``visible`` já editado pelo
    admin; remove operações que sumiram do spec. Devolve contadores. Injeta a
    master key da API no fetch, caso o ``openapi.json`` seja protegido.
    """
    api = await get_api_by_id(db, api_id)
    if not api.openapi_url:
        raise DocsNotConfiguredError("API sem openapi_url configurada")

    parsed = await fetch_spec_docs(
        api.openapi_url, auth_headers=_doc_fetch_auth_headers(api)
    )
    operations = parsed.get("operations", [])

    result = await db.execute(
        select(ApiDocOperation).where(ApiDocOperation.api_id == api.id)
    )
    existing = {(row.method, row.path): row for row in result.scalars().all()}

    seen: set = set()
    created = updated = 0
    for idx, op in enumerate(operations):
        key = (op["method"], op["path"])
        seen.add(key)
        payload = _doc_payload(op)
        row = existing.get(key)
        if row is not None:
            row.summary = op.get("summary")
            row.description = op.get("description")
            row.operation_json = payload
            row.sort_order = idx
            updated += 1
        else:
            db.add(
                ApiDocOperation(
                    api_id=api.id,
                    method=op["method"],
                    path=op["path"],
                    summary=op.get("summary"),
                    description=op.get("description"),
                    operation_json=payload,
                    visible=True,
                    sort_order=idx,
                )
            )
            created += 1

    removed = 0
    for key, row in existing.items():
        if key not in seen:
            await db.delete(row)
            removed += 1

    await db.commit()
    return {
        "created": created,
        "updated": updated,
        "removed": removed,
        "total": len(operations),
    }


async def list_doc_operations(
    db: AsyncSession, api_id: object, only_visible: bool = False
) -> list[ApiDocOperation]:
    stmt = select(ApiDocOperation).where(ApiDocOperation.api_id == api_id)
    if only_visible:
        stmt = stmt.where(ApiDocOperation.visible.is_(True))
    stmt = stmt.order_by(ApiDocOperation.sort_order, ApiDocOperation.path)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def set_doc_operation_visibility(
    db: AsyncSession, api_id: str, op_id: str, visible: bool
) -> ApiDocOperation:
    result = await db.execute(
        select(ApiDocOperation).where(
            ApiDocOperation.id == uuid.UUID(str(op_id)),
            ApiDocOperation.api_id == uuid.UUID(str(api_id)),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise DocOperationNotFoundError(f"Doc operation not found: {op_id}")
    row.visible = visible
    await db.commit()
    await db.refresh(row)
    return row


async def api_ids_with_visible_docs(
    db: AsyncSession, api_ids: list[uuid.UUID]
) -> set[uuid.UUID]:
    """Subconjunto de ``api_ids`` que têm ≥1 operação de doc visível."""
    if not api_ids:
        return set()
    result = await db.execute(
        select(ApiDocOperation.api_id)
        .where(
            ApiDocOperation.api_id.in_(api_ids),
            ApiDocOperation.visible.is_(True),
        )
        .distinct()
    )
    return set(result.scalars().all())
