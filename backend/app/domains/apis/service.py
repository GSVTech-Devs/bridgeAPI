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


async def register_api(
    db: AsyncSession,
    name: str,
    base_url: str,
    master_key: str | None = None,
    auth_type: APIAuthType = APIAuthType.NONE,
) -> ExternalAPI:
    existing = await db.execute(select(ExternalAPI).where(ExternalAPI.name == name))
    if existing.scalar_one_or_none() is not None:
        raise DuplicateAPINameError(f"API name already registered: {name}")

    encrypted = encrypt_value(master_key) if master_key is not None else None
    api = ExternalAPI(
        name=name,
        base_url=base_url,
        master_key_encrypted=encrypted,
        auth_type=auth_type,
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


async def list_endpoints_for_api(db: AsyncSession, api_id: object) -> list[Endpoint]:
    result = await db.execute(select(Endpoint).where(Endpoint.api_id == api_id))
    return list(result.scalars().all())
