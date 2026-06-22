from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import Feature
from app.core.database import get_db
from app.domains.auth.router import require_feature
from app.domains.auth.schemas import MeResponse
from app.domains.keys.schemas import (
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyListResponse,
    APIKeyResponse,
)
from app.domains.keys.service import (
    APIKeyLimitExceededError,
    APIKeyNotFoundError,
    UnauthorizedApiError,
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
    identity: MeResponse = Depends(require_feature(Feature.KEYS_ROTATE)),
) -> APIKeyCreateResponse:
    try:
        api_key, plain_secret = await create_api_key(
            db, identity.account_id, body.name, api_id=body.api_id
        )
    except UnauthorizedApiError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active permission for this API",
        )
    except APIKeyLimitExceededError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Maximum of 5 active keys per API reached. "
                "Revoke a key before creating a new one."
            ),
        )
    return APIKeyCreateResponse(
        **APIKeyResponse.model_validate(api_key).model_dump(exclude={"api_key"}),
        api_key=plain_secret,
    )


@router.get("", response_model=APIKeyListResponse)
async def list_all(
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(require_feature(Feature.API_KEYS)),
) -> APIKeyListResponse:
    pairs = await list_api_keys(db, identity.account_id)
    items = []
    for api_key, plain_secret in pairs:
        data = APIKeyResponse.model_validate(api_key).model_dump()
        data["api_key"] = plain_secret
        items.append(APIKeyResponse(**data))
    return APIKeyListResponse(items=items)


@router.patch("/{key_id}/revoke", response_model=APIKeyResponse)
async def revoke(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(require_feature(Feature.KEYS_ROTATE)),
) -> APIKeyResponse:
    try:
        api_key = await revoke_api_key(db, identity.account_id, str(key_id))
    except APIKeyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    return APIKeyResponse.model_validate(api_key)
