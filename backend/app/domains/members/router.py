from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.accounts.models import AccountType
from app.domains.accounts.service import AccountNotFoundError, get_account_by_id
from app.domains.auth.models import UserRole
from app.domains.auth.router import get_current_account_user, get_current_user
from app.domains.auth.schemas import MeResponse
from app.domains.auth.service import DuplicateEmailError
from app.domains.members.schemas import (
    MemberCreate,
    MemberListResponse,
    MemberResponse,
    MemberUpdate,
    RoleCreate,
    RoleListResponse,
    RoleResponse,
    RoleUpdate,
)
from app.domains.members.service import (
    MemberNotFoundError,
    PasswordRequiredError,
    RoleInUseError,
    RoleNameConflictError,
    RoleNotFoundError,
    SharedIdentityError,
    create_member,
    create_role,
    delete_member,
    delete_role,
    list_members,
    list_roles,
    update_member,
    update_role,
)

router = APIRouter(prefix="/portal", tags=["members"])


async def get_current_company_owner(
    identity: MeResponse = Depends(get_current_account_user),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    """Exige o responsável (owner) de uma account do tipo empresa.

    Gestão de usuários/roles é exclusiva de empresas e do seu owner.
    """
    if identity.role != UserRole.OWNER.value or identity.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    try:
        account = await get_account_by_id(db, str(identity.account_id))
    except AccountNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    if account.type != AccountType.COMPANY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Gestão de usuários disponível apenas para empresas.",
        )
    return identity


def _role_response(role, member_count: int = 0) -> RoleResponse:
    return RoleResponse(
        id=role.id,
        name=role.name,
        capabilities=list(role.capabilities or []),
        member_count=member_count,
        created_at=role.created_at,
    )


def _member_response(member, role_name: str | None) -> MemberResponse:
    return MemberResponse(
        id=member.id,
        email=member.email,
        role_id=member.role_id,
        role_name=role_name,
        created_at=member.created_at,
    )


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------
@router.get("/roles", response_model=RoleListResponse)
async def list_account_roles(
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(get_current_company_owner),
) -> RoleListResponse:
    rows = await list_roles(db, identity.account_id)
    return RoleListResponse(
        items=[_role_response(role, count) for role, count in rows]
    )


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_account_role(
    body: RoleCreate,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(get_current_company_owner),
) -> RoleResponse:
    try:
        role = await create_role(
            db,
            account_id=identity.account_id,
            name=body.name,
            capabilities=body.capabilities,
        )
    except RoleNameConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Role já existe"
        )
    return _role_response(role)


@router.patch("/roles/{role_id}", response_model=RoleResponse)
async def update_account_role(
    role_id: uuid.UUID,
    body: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(get_current_company_owner),
) -> RoleResponse:
    try:
        role = await update_role(
            db,
            account_id=identity.account_id,
            role_id=role_id,
            name=body.name,
            capabilities=body.capabilities,
        )
    except RoleNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role não encontrada"
        )
    except RoleNameConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Role já existe"
        )
    return _role_response(role)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account_role(
    role_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(get_current_company_owner),
) -> None:
    try:
        await delete_role(db, account_id=identity.account_id, role_id=role_id)
    except RoleNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role não encontrada"
        )
    except RoleInUseError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


# ---------------------------------------------------------------------------
# Membros
# ---------------------------------------------------------------------------
@router.get("/members", response_model=MemberListResponse)
async def list_account_members(
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(get_current_company_owner),
) -> MemberListResponse:
    rows = await list_members(db, identity.account_id)
    return MemberListResponse(
        items=[_member_response(member, role_name) for member, role_name in rows]
    )


@router.post(
    "/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED
)
async def create_account_member(
    body: MemberCreate,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(get_current_company_owner),
) -> MemberResponse:
    try:
        member = await create_member(
            db,
            account_id=identity.account_id,
            email=body.email,
            password=body.password,
            role_id=body.role_id,
        )
    except RoleNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role não encontrada"
        )
    except PasswordRequiredError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except SharedIdentityError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except DuplicateEmailError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )
    return _member_response(member, None)


@router.patch("/members/{member_id}", response_model=MemberResponse)
async def update_account_member(
    member_id: uuid.UUID,
    body: MemberUpdate,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(get_current_company_owner),
) -> MemberResponse:
    try:
        member = await update_member(
            db,
            account_id=identity.account_id,
            member_id=member_id,
            email=body.email,
            password=body.password,
            role_id=body.role_id,
        )
    except MemberNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Membro não encontrado"
        )
    except RoleNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role não encontrada"
        )
    except PasswordRequiredError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except SharedIdentityError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except DuplicateEmailError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )
    return _member_response(member, None)


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account_member(
    member_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(get_current_company_owner),
) -> None:
    try:
        await delete_member(db, account_id=identity.account_id, member_id=member_id)
    except MemberNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Membro não encontrado"
        )


# ===========================================================================
# Gestão pelo admin da plataforma (espelha as rotas /portal acima, mas para
# qualquer empresa, identificada por account_id na URL). Mesmo service, mesma
# semântica de autorização — só muda quem pode chamar (admin) e o escopo.
# ===========================================================================
admin_router = APIRouter(prefix="/admin/accounts", tags=["members-admin"])


async def _admin_company_account_id(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: MeResponse = Depends(get_current_user),
) -> uuid.UUID:
    """Admin da plataforma gerenciando roles/membros de uma empresa.

    Exige admin (via `get_current_user`) e que a account exista e seja do tipo
    empresa — gestão de usuários só faz sentido para empresas.
    """
    try:
        account = await get_account_by_id(db, str(account_id))
    except AccountNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    if account.type != AccountType.COMPANY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gestão de usuários disponível apenas para empresas.",
        )
    return account_id


# --- Roles -----------------------------------------------------------------
@admin_router.get("/{account_id}/roles", response_model=RoleListResponse)
async def admin_list_roles(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: uuid.UUID = Depends(_admin_company_account_id),
) -> RoleListResponse:
    rows = await list_roles(db, account_id)
    return RoleListResponse(
        items=[_role_response(role, count) for role, count in rows]
    )


@admin_router.post(
    "/{account_id}/roles",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_role(
    account_id: uuid.UUID,
    body: RoleCreate,
    db: AsyncSession = Depends(get_db),
    _: uuid.UUID = Depends(_admin_company_account_id),
) -> RoleResponse:
    try:
        role = await create_role(
            db, account_id=account_id, name=body.name, capabilities=body.capabilities
        )
    except RoleNameConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Role já existe"
        )
    return _role_response(role)


@admin_router.patch("/{account_id}/roles/{role_id}", response_model=RoleResponse)
async def admin_update_role(
    account_id: uuid.UUID,
    role_id: uuid.UUID,
    body: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    _: uuid.UUID = Depends(_admin_company_account_id),
) -> RoleResponse:
    try:
        role = await update_role(
            db,
            account_id=account_id,
            role_id=role_id,
            name=body.name,
            capabilities=body.capabilities,
        )
    except RoleNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role não encontrada"
        )
    except RoleNameConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Role já existe"
        )
    return _role_response(role)


@admin_router.delete(
    "/{account_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def admin_delete_role(
    account_id: uuid.UUID,
    role_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: uuid.UUID = Depends(_admin_company_account_id),
) -> None:
    try:
        await delete_role(db, account_id=account_id, role_id=role_id)
    except RoleNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role não encontrada"
        )
    except RoleInUseError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


# --- Membros ---------------------------------------------------------------
@admin_router.get("/{account_id}/members", response_model=MemberListResponse)
async def admin_list_members(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: uuid.UUID = Depends(_admin_company_account_id),
) -> MemberListResponse:
    rows = await list_members(db, account_id)
    return MemberListResponse(
        items=[_member_response(member, role_name) for member, role_name in rows]
    )


@admin_router.post(
    "/{account_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_member(
    account_id: uuid.UUID,
    body: MemberCreate,
    db: AsyncSession = Depends(get_db),
    _: uuid.UUID = Depends(_admin_company_account_id),
) -> MemberResponse:
    try:
        member = await create_member(
            db,
            account_id=account_id,
            email=body.email,
            password=body.password,
            role_id=body.role_id,
        )
    except RoleNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role não encontrada"
        )
    except PasswordRequiredError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except SharedIdentityError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except DuplicateEmailError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )
    return _member_response(member, None)


@admin_router.patch(
    "/{account_id}/members/{member_id}", response_model=MemberResponse
)
async def admin_update_member(
    account_id: uuid.UUID,
    member_id: uuid.UUID,
    body: MemberUpdate,
    db: AsyncSession = Depends(get_db),
    _: uuid.UUID = Depends(_admin_company_account_id),
) -> MemberResponse:
    try:
        member = await update_member(
            db,
            account_id=account_id,
            member_id=member_id,
            email=body.email,
            password=body.password,
            role_id=body.role_id,
        )
    except MemberNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Membro não encontrado"
        )
    except RoleNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role não encontrada"
        )
    except PasswordRequiredError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except SharedIdentityError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except DuplicateEmailError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )
    return _member_response(member, None)


@admin_router.delete(
    "/{account_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def admin_delete_member(
    account_id: uuid.UUID,
    member_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: uuid.UUID = Depends(_admin_company_account_id),
) -> None:
    try:
        await delete_member(db, account_id=account_id, member_id=member_id)
    except MemberNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Membro não encontrado"
        )
