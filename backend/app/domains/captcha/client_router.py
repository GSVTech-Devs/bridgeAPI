"""Autosserviço de captcha do cliente, por API. Espelha o client_router de proxy:
só gerencia quando o admin habilitou ``captcha_managed_by_client`` na permissão
(e o cliente tem ``Feature.CAPTCHA``)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import Feature
from app.core.database import get_db
from app.domains.apis.service import APINotFoundError
from app.domains.auth.router import require_feature
from app.domains.auth.schemas import MeResponse
from app.domains.captcha.schemas import (
    CaptchaCreate,
    CaptchaListResponse,
    CaptchaResponse,
    CaptchaUpdate,
)
from app.domains.captcha.service import (
    CaptchaNotFoundError,
    create_captcha,
    delete_captcha,
    get_scoped_captcha,
    list_api_captchas,
    to_response,
    update_captcha,
)
from app.domains.permissions.service import get_permission

router = APIRouter(prefix="/client/apis", tags=["captcha-client"])

_require = require_feature(Feature.CAPTCHA)


async def _ensure_managed(db: AsyncSession, identity: MeResponse, api_id: uuid.UUID):
    perm = await get_permission(db, str(identity.account_id), str(api_id))
    if perm is None or not perm.captcha_managed_by_client:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Captcha management not enabled for this API",
        )


@router.get("/{api_id}/captchas", response_model=CaptchaListResponse)
async def list_route(
    api_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(_require),
) -> CaptchaListResponse:
    await _ensure_managed(db, identity, api_id)
    items = await list_api_captchas(db, str(api_id), account_id=identity.account_id)
    return CaptchaListResponse(items=[to_response(c) for c in items], total=len(items))


@router.post(
    "/{api_id}/captchas", response_model=CaptchaResponse, status_code=status.HTTP_201_CREATED
)
async def create_route(
    api_id: uuid.UUID,
    body: CaptchaCreate,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(_require),
) -> CaptchaResponse:
    await _ensure_managed(db, identity, api_id)
    try:
        captcha = await create_captcha(db, str(api_id), body, account_id=identity.account_id)
    except APINotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API not found")
    return to_response(captcha)


@router.patch("/{api_id}/captchas/{captcha_id}", response_model=CaptchaResponse)
async def update_route(
    api_id: uuid.UUID,
    captcha_id: uuid.UUID,
    body: CaptchaUpdate,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(_require),
) -> CaptchaResponse:
    await _ensure_managed(db, identity, api_id)
    try:
        captcha = await get_scoped_captcha(
            db, str(captcha_id), str(api_id), account_id=identity.account_id
        )
        captcha = await update_captcha(db, captcha, body)
    except CaptchaNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Captcha provider not found")
    return to_response(captcha)


@router.delete(
    "/{api_id}/captchas/{captcha_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_route(
    api_id: uuid.UUID,
    captcha_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(_require),
) -> None:
    await _ensure_managed(db, identity, api_id)
    try:
        captcha = await get_scoped_captcha(
            db, str(captcha_id), str(api_id), account_id=identity.account_id
        )
    except CaptchaNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Captcha provider not found")
    await delete_captcha(db, captcha)
