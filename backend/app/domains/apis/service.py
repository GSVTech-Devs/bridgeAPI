from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import encrypt_value
from app.domains.apis.models import (
    APIAuthType,
    APIStatus,
    Endpoint,
    ExternalAPI,
    HTTPMethod,
)


class DuplicateAPINameError(Exception):
    pass


class APINotFoundError(Exception):
    pass


class DuplicateSlugError(Exception):
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
    )
    db.add(api)
    await db.commit()
    await db.refresh(api)
    return api


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
