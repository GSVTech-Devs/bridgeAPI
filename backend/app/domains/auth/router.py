from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import Feature
from app.core.database import get_db
from app.core.security import create_access_token, decode_access_token
from app.domains.accounts.models import AccountStatus
from app.domains.accounts.service import AccountNotFoundError, get_account_by_id
from app.domains.auth.models import UserRole
from app.domains.auth.schemas import (
    ChangePasswordRequest,
    CompaniesResponse,
    CompanyOption,
    LoginRequest,
    MeResponse,
    PortalLoginResponse,
    SelectCompanyRequest,
    TokenResponse,
)
from app.domains.auth.service import (
    InvalidCurrentPasswordError,
    UserNotFoundError,
    authenticate_user,
    change_user_password,
    get_account_user,
    get_users_by_email,
)
from app.domains.members.service import resolve_user_capabilities

router = APIRouter(prefix="/auth", tags=["auth"])

bearer = HTTPBearer()

_ACCOUNT_ROLES = {UserRole.OWNER.value, UserRole.MEMBER.value}
# Token emitido logo após o login do portal, antes de escolher a empresa:
# autentica a identidade (email) mas não dá acesso a nenhuma account até que
# uma seja selecionada via /auth/portal/select.
_PORTAL_IDENTITY_ROLE = "portal_identity"


async def _portal_companies(db: AsyncSession, email: str) -> list[CompanyOption]:
    """Empresas ativas acessíveis por um email (para o seletor de empresa)."""
    companies: list[CompanyOption] = []
    for user in await get_users_by_email(db, email):
        if user.role not in _ACCOUNT_ROLES or user.account_id is None:
            continue
        try:
            account = await get_account_by_id(db, str(user.account_id))
        except AccountNotFoundError:
            continue
        if account.status != AccountStatus.ACTIVE:
            continue
        companies.append(
            CompanyOption(
                account_id=account.id,
                name=account.name,
                type=account.type,
                role=user.role,
            )
        )
    return companies


def _build_identity(credentials: HTTPAuthorizationCredentials) -> MeResponse:
    payload = decode_access_token(credentials.credentials)
    return MeResponse(
        email=payload["sub"],
        role=payload.get("role", UserRole.ADMIN.value),
        user_id=payload.get("user_id"),
        account_id=payload.get("account_id"),
    )


def _decode_or_401(credentials: HTTPAuthorizationCredentials) -> MeResponse:
    try:
        return _build_identity(credentials)
    except (JWTError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_identity(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> MeResponse:
    """Qualquer token válido (admin ou usuário de account)."""
    return _decode_or_401(credentials)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> MeResponse:
    """Exige admin da plataforma."""
    identity = _decode_or_401(credentials)
    if identity.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return identity


async def get_current_account_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> MeResponse:
    """Exige usuário vinculado a uma account (owner ou member)."""
    identity = _decode_or_401(credentials)
    if identity.role not in _ACCOUNT_ROLES or identity.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return identity


def require_feature(feature: Feature):
    """Dependency que exige uma capability de dashboard.

    As capabilities são resolvidas ao vivo do banco (papel + role do membro),
    de modo que mudanças nas toggles do owner valem imediatamente e não há
    como forjar permissões pelo token.
    """

    async def _dep(
        identity: MeResponse = Depends(get_current_account_user),
        db: AsyncSession = Depends(get_db),
    ) -> MeResponse:
        capabilities = await resolve_user_capabilities(db, identity)
        if feature.value not in capabilities:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Feature not allowed: {feature.value}",
            )
        return identity

    return _dep


# Mensagem genérica de falha de login. Mesma resposta para email inexistente,
# senha errada, conta de tipo errado ou sem empresa ativa — para não revelar se
# um email/empresa existe (evita enumeração de usuários).
_INVALID_CREDENTIALS = "Email ou senha inválidos."


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Login do admin da plataforma."""
    user = await authenticate_user(db, body.email, body.password)
    if user is None or user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(
        user.email, role=user.role, extra_claims={"user_id": str(user.id)}
    )
    return TokenResponse(access_token=token)


async def get_portal_identity(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> str:
    """Identidade do portal (email) a partir de qualquer token válido seu.

    Aceita tanto o token de identidade (pós-login, sem empresa) quanto um
    token já escopado a uma empresa — ambos carregam o email em ``sub``. Exige
    que o email tenha ao menos um vínculo de portal (owner/member).
    """
    identity = _decode_or_401(credentials)
    users = await get_users_by_email(db, identity.email)
    if not any(u.role in _ACCOUNT_ROLES and u.account_id for u in users):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return identity.email


@router.post("/portal/login", response_model=PortalLoginResponse)
async def portal_login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> PortalLoginResponse:
    """Login dos usuários de account (responsável/membro).

    Como um mesmo email pode acessar várias empresas, o login devolve a lista
    de empresas + um token de identidade; o frontend seleciona uma empresa via
    ``/auth/portal/select`` (ou entra direto quando há só uma).
    """
    user = await authenticate_user(db, body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )
    companies = await _portal_companies(db, body.email)
    if not companies:
        # Email autenticou mas não tem nenhuma empresa ativa (sem vínculo de
        # portal ou todas bloqueadas). Resposta genérica de propósito: não
        # revelamos que a credencial era válida (anti-enumeração).
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(body.email, role=_PORTAL_IDENTITY_ROLE)
    return PortalLoginResponse(access_token=token, companies=companies)


@router.get("/portal/companies", response_model=CompaniesResponse)
async def portal_companies(
    email: str = Depends(get_portal_identity),
    db: AsyncSession = Depends(get_db),
) -> CompaniesResponse:
    """Empresas que o usuário logado pode acessar (para o seletor / troca)."""
    return CompaniesResponse(companies=await _portal_companies(db, email))


@router.post("/portal/select", response_model=TokenResponse)
async def portal_select(
    body: SelectCompanyRequest,
    email: str = Depends(get_portal_identity),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Emite o token escopado a uma empresa escolhida (sem reentrar a senha).

    Usado tanto na seleção pós-login quanto na troca de empresa já logado.
    """
    user = await get_account_user(db, body.account_id, email)
    if user is None or user.role not in _ACCOUNT_ROLES or user.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem acesso a esta empresa.",
        )
    try:
        account = await get_account_by_id(db, str(user.account_id))
    except AccountNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem acesso a esta empresa.",
        )
    if account.status != AccountStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {account.status}. Contact the administrator.",
        )
    token = create_access_token(
        email,
        role=user.role,
        extra_claims={"user_id": str(user.id), "account_id": str(user.account_id)},
    )
    return TokenResponse(access_token=token)


@router.patch("/portal/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_portal_password(
    body: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    identity: MeResponse = Depends(get_current_account_user),
) -> None:
    """Troca de senha self-service do usuário do portal (não altera o email)."""
    if identity.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    try:
        await change_user_password(
            db,
            user_id=identity.user_id,
            current_password=body.current_password,
            new_password=body.new_password,
        )
    except InvalidCurrentPasswordError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )


@router.get("/me", response_model=MeResponse)
async def me(
    current: MeResponse = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    """Identidade do usuário logado + capabilities efetivas (para a UI)."""
    current.capabilities = sorted(await resolve_user_capabilities(db, current))
    current.is_owner = current.role == UserRole.OWNER.value
    if current.account_id is not None:
        try:
            account = await get_account_by_id(db, str(current.account_id))
            current.account_type = account.type
            current.account_name = account.name
        except AccountNotFoundError:
            current.account_type = None
            current.account_name = None
    if current.role in _ACCOUNT_ROLES:
        # Quantas empresas ativas este email acessa — habilita "Trocar empresa".
        current.account_count = len(await _portal_companies(db, current.email))
    return current
