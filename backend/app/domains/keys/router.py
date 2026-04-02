from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.router import get_current_client
from app.domains.auth.schemas import MeResponse
from app.domains.keys.schemas import (
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyListResponse,
    APIKeyResponse,
)
from app.domains.keys.service import (
    APIKeyNotFoundError,
    create_api_key,
    list_api_keys,
    revoke_api_key,
)

router = APIRouter(prefix="/keys", tags=["keys"])


@router.post(
    "",
    response_model=APIKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create(
    body: APIKeyCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_client: MeResponse = Depends(get_current_client),
) -> APIKeyCreateResponse:
    api_key, plain_secret = await create_api_key(db, current_client.email, body.name)
    return APIKeyCreateResponse(
        **APIKeyResponse.model_validate(api_key).model_dump(),
        api_key=plain_secret,
    )


@router.get("", response_model=APIKeyListResponse)
async def list_all(
    db: AsyncSession = Depends(get_db),
    current_client: MeResponse = Depends(get_current_client),
) -> APIKeyListResponse:
    api_keys = await list_api_keys(db, current_client.email)
    return APIKeyListResponse(
        items=[APIKeyResponse.model_validate(api_key) for api_key in api_keys]
    )


@router.patch("/{key_id}/revoke", response_model=APIKeyResponse)
async def revoke(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_client: MeResponse = Depends(get_current_client),
) -> APIKeyResponse:
    try:
        api_key = await revoke_api_key(db, current_client.email, str(key_id))
    except APIKeyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    return APIKeyResponse.model_validate(api_key)
