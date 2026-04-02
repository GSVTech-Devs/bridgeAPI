from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token
from app.domains.auth.router import get_current_user
from app.domains.auth.schemas import MeResponse, TokenResponse
from app.domains.clients.models import ClientStatus
from app.domains.clients.schemas import (
    ClientListResponse,
    ClientLoginRequest,
    ClientRegisterRequest,
    ClientResponse,
)
from app.domains.clients.service import (
    ClientNotFoundError,
    DuplicateEmailError,
    InvalidStatusTransitionError,
    approve_client,
    authenticate_client,
    list_clients,
    register_client,
    reject_client,
)

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post(
    "/register",
    response_model=ClientResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    body: ClientRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    try:
        client = await register_client(db, body.name, body.email, body.password)
    except DuplicateEmailError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    return ClientResponse.model_validate(client)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: ClientLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    client = await authenticate_client(db, body.email, body.password)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if client.status != ClientStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {client.status}. Wait for admin approval.",
        )
    return TokenResponse(access_token=create_access_token(client.email, role="client"))


@router.get("", response_model=ClientListResponse)
async def list_all(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> ClientListResponse:
    clients, total = await list_clients(db, page, per_page)
    return ClientListResponse(
        items=[ClientResponse.model_validate(c) for c in clients],
        total=total,
    )


@router.patch("/{client_id}/approve", response_model=ClientResponse)
async def approve(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> ClientResponse:
    try:
        client = await approve_client(db, str(client_id))
    except ClientNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        )
    except InvalidStatusTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return ClientResponse.model_validate(client)


@router.patch("/{client_id}/reject", response_model=ClientResponse)
async def reject(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> ClientResponse:
    try:
        client = await reject_client(db, str(client_id))
    except ClientNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        )
    except InvalidStatusTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return ClientResponse.model_validate(client)
