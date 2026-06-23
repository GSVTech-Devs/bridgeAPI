from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.apis.service import APINotFoundError
from app.domains.auth.router import get_current_user
from app.domains.auth.schemas import MeResponse
from app.domains.captcha.schemas import (
    CaptchaCreate,
    CaptchaListResponse,
    CaptchaMonitorResponse,
    CaptchaResponse,
    CaptchaUpdate,
)
from app.domains.captcha.service import (
    CaptchaNotFoundError,
    create_captcha,
    delete_captcha,
    get_scoped_captcha,
    list_api_captchas,
    monitor_captchas,
    to_response,
    update_captcha,
)

# Provedores de captcha do admin para uma API, aninhados no recurso da API.
router = APIRouter(prefix="/apis", tags=["captcha"])


@router.get("/{api_id}/captchas", response_model=CaptchaListResponse)
async def list_route(
    api_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> CaptchaListResponse:
    items = await list_api_captchas(db, str(api_id), account_id=None)
    return CaptchaListResponse(items=[to_response(c) for c in items], total=len(items))


@router.post(
    "/{api_id}/captchas", response_model=CaptchaResponse, status_code=status.HTTP_201_CREATED
)
async def create_route(
    api_id: uuid.UUID,
    body: CaptchaCreate,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> CaptchaResponse:
    try:
        captcha = await create_captcha(db, str(api_id), body, account_id=None)
    except APINotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API not found")
    return to_response(captcha)


@router.patch("/{api_id}/captchas/{captcha_id}", response_model=CaptchaResponse)
async def update_route(
    api_id: uuid.UUID,
    captcha_id: uuid.UUID,
    body: CaptchaUpdate,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> CaptchaResponse:
    try:
        captcha = await get_scoped_captcha(db, str(captcha_id), str(api_id), account_id=None)
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
    _: MeResponse = Depends(get_current_user),
) -> None:
    try:
        captcha = await get_scoped_captcha(db, str(captcha_id), str(api_id), account_id=None)
    except CaptchaNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Captcha provider not found")
    await delete_captcha(db, captcha)


# ----------------------------------------------------------- monitoramento
monitor_router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@monitor_router.get("/captchas", response_model=CaptchaMonitorResponse)
async def monitor_captchas_route(
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> CaptchaMonitorResponse:
    items = await monitor_captchas(db)
    return CaptchaMonitorResponse(items=items, total=len(items))
