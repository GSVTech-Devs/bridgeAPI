from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.accounts.schemas import (
    AccountListResponse,
    AccountResponse,
    AccountWithOwnerResponse,
    CreateCompanyRequest,
    CreateIndividualRequest,
)
from app.domains.accounts.service import (
    AccountNotFoundError,
    InvalidStatusTransitionError,
    block_account,
    create_company,
    create_individual,
    list_accounts,
    unblock_account,
)
from app.domains.auth.router import get_current_user
from app.domains.auth.schemas import MeResponse
from app.domains.auth.service import DuplicateEmailError

router = APIRouter(prefix="/admin", tags=["accounts"])


def _with_owner(account, owner) -> AccountWithOwnerResponse:
    return AccountWithOwnerResponse(
        account=AccountResponse.model_validate(account),
        owner_email=owner.email,
        owner_id=owner.id,
    )


@router.post(
    "/users",
    response_model=AccountWithOwnerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_individual_user(
    body: CreateIndividualRequest,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> AccountWithOwnerResponse:
    """Cria um usuário avulso (account individual + responsável)."""
    try:
        account, owner = await create_individual(
            db, name=body.name, email=body.email, password=body.password
        )
    except DuplicateEmailError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )
    return _with_owner(account, owner)


@router.post(
    "/companies",
    response_model=AccountWithOwnerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_company_account(
    body: CreateCompanyRequest,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> AccountWithOwnerResponse:
    """Cria uma empresa + usuário responsável inicial."""
    try:
        account, owner = await create_company(
            db,
            company_name=body.company_name,
            owner_email=body.owner_email,
            owner_password=body.owner_password,
        )
    except DuplicateEmailError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )
    return _with_owner(account, owner)


@router.get("/accounts", response_model=AccountListResponse)
async def list_all(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> AccountListResponse:
    accounts, total = await list_accounts(db, page, per_page)
    return AccountListResponse(
        items=[AccountResponse.model_validate(a) for a in accounts],
        total=total,
    )


@router.patch("/accounts/{account_id}/block", response_model=AccountResponse)
async def block(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> AccountResponse:
    try:
        account = await block_account(db, str(account_id))
    except AccountNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    except InvalidStatusTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return AccountResponse.model_validate(account)


@router.patch("/accounts/{account_id}/unblock", response_model=AccountResponse)
async def unblock(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> AccountResponse:
    try:
        account = await unblock_account(db, str(account_id))
    except AccountNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    except InvalidStatusTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return AccountResponse.model_validate(account)
