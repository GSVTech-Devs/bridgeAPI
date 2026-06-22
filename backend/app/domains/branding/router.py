from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.accounts.service import AccountNotFoundError, get_account_by_id
from app.domains.auth.models import UserRole
from app.domains.auth.router import get_current_account_user
from app.domains.auth.schemas import MeResponse
from app.domains.branding.schemas import BrandingResponse
from app.domains.branding.service import (
    MAX_LOGO_BYTES,
    InvalidLogoError,
    clear_account_logo,
    logo_data_uri,
    set_account_logo,
    validate_logo,
)

router = APIRouter(prefix="/portal/branding", tags=["branding"])


async def get_current_account_owner(
    identity: MeResponse = Depends(get_current_account_user),
) -> MeResponse:
    """Exige o responsável (owner) da account — empresa ou individual.

    A identidade visual é da conta, então só o owner a gerencia; membros
    apenas a enxergam (via ``GET /portal/branding``).
    """
    if identity.role != UserRole.OWNER.value or identity.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return identity


@router.get("", response_model=BrandingResponse)
async def get_account_branding(
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(get_current_account_user),
) -> BrandingResponse:
    """Identidade visual da conta do usuário logado (qualquer usuário)."""
    try:
        account = await get_account_by_id(db, str(identity.account_id))
    except AccountNotFoundError:
        return BrandingResponse(logo_data_uri=None)
    return BrandingResponse(logo_data_uri=logo_data_uri(account))


@router.put("/logo", response_model=BrandingResponse)
async def upload_account_logo(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(get_current_account_owner),
) -> BrandingResponse:
    """Faz upload/substitui a logo da conta. Valida formato, tamanho e conteúdo."""
    if file.size is not None and file.size > MAX_LOGO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Arquivo muito grande. O limite é 5 MB.",
        )
    data = await file.read()
    try:
        content_type = validate_logo(file.content_type, data)
    except InvalidLogoError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    try:
        account = await set_account_logo(
            db, str(identity.account_id), content_type=content_type, data=data
        )
    except AccountNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    return BrandingResponse(logo_data_uri=logo_data_uri(account))


@router.delete("/logo", response_model=BrandingResponse)
async def delete_account_logo(
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(get_current_account_owner),
) -> BrandingResponse:
    """Remove a logo da conta, voltando à marca padrão."""
    try:
        account = await clear_account_logo(db, str(identity.account_id))
    except AccountNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    return BrandingResponse(logo_data_uri=logo_data_uri(account))
