from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import BASELINE_MEMBER_FEATURES, OWNER_FEATURES
from app.core.security import hash_password
from app.domains.auth.models import User, UserRole
from app.domains.auth.service import (
    DuplicateEmailError,
    get_user_by_id,
    get_users_by_email,
)
from app.domains.members.models import AccountRole


class RoleNotFoundError(Exception):
    pass


class RoleNameConflictError(Exception):
    pass


class RoleInUseError(Exception):
    pass


class MemberNotFoundError(Exception):
    pass


class PasswordRequiredError(Exception):
    """Email novo na plataforma — é preciso definir uma senha inicial."""


class SharedIdentityError(Exception):
    """O email do membro também pertence a outras empresas; a credencial é
    compartilhada e gerida pela própria identidade, não pelo owner."""


# ---------------------------------------------------------------------------
# Resolução de capabilities (usada pelo require_feature)
# ---------------------------------------------------------------------------
async def resolve_user_capabilities(db: AsyncSession, identity) -> set[str]:
    """Capabilities efetivas de um usuário de account, resolvidas ao vivo.

    - owner → todas as features.
    - member → baseline + capabilities da sua role (lida do banco).
    - admin/none → vazio.
    """
    role = identity.role
    if role == UserRole.OWNER.value:
        return {f.value for f in OWNER_FEATURES}
    if role == UserRole.MEMBER.value:
        caps = {f.value for f in BASELINE_MEMBER_FEATURES}
        if identity.user_id is not None:
            user = await get_user_by_id(db, identity.user_id)
            if user is not None and user.role_id is not None:
                role_obj = await db.get(AccountRole, user.role_id)
                if role_obj is not None:
                    caps |= set(role_obj.capabilities or [])
        return caps
    return set()


# ---------------------------------------------------------------------------
# Roles (escopadas à account)
# ---------------------------------------------------------------------------
async def _get_role_for_account(
    db: AsyncSession, account_id: uuid.UUID | str, role_id: uuid.UUID | str
) -> AccountRole | None:
    result = await db.execute(
        select(AccountRole).where(
            AccountRole.id == role_id,
            AccountRole.account_id == account_id,
        )
    )
    return result.scalar_one_or_none()


async def _role_name_taken(
    db: AsyncSession,
    account_id: uuid.UUID | str,
    name: str,
    *,
    exclude_id: uuid.UUID | str | None = None,
) -> bool:
    stmt = select(AccountRole.id).where(
        AccountRole.account_id == account_id,
        AccountRole.name == name,
    )
    if exclude_id is not None:
        stmt = stmt.where(AccountRole.id != exclude_id)
    result = await db.execute(stmt)
    return result.first() is not None


async def create_role(
    db: AsyncSession,
    *,
    account_id: uuid.UUID | str,
    name: str,
    capabilities: list[str],
) -> AccountRole:
    if await _role_name_taken(db, account_id, name):
        raise RoleNameConflictError(f"Role já existe: {name}")
    role = AccountRole(
        account_id=uuid.UUID(str(account_id)),
        name=name,
        capabilities=capabilities,
    )
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return role


async def list_roles(
    db: AsyncSession, account_id: uuid.UUID | str
) -> list[tuple[AccountRole, int]]:
    result = await db.execute(
        select(AccountRole, func.count(User.id))
        .outerjoin(User, User.role_id == AccountRole.id)
        .where(AccountRole.account_id == account_id)
        .group_by(AccountRole.id)
        .order_by(AccountRole.created_at.asc())
    )
    return [(row[0], row[1]) for row in result.all()]


async def update_role(
    db: AsyncSession,
    *,
    account_id: uuid.UUID | str,
    role_id: uuid.UUID | str,
    name: str | None = None,
    capabilities: list[str] | None = None,
) -> AccountRole:
    role = await _get_role_for_account(db, account_id, role_id)
    if role is None:
        raise RoleNotFoundError(f"Role não encontrada: {role_id}")
    if name is not None and name != role.name:
        if await _role_name_taken(db, account_id, name, exclude_id=role.id):
            raise RoleNameConflictError(f"Role já existe: {name}")
        role.name = name
    if capabilities is not None:
        role.capabilities = capabilities
    await db.commit()
    await db.refresh(role)
    return role


async def _role_member_count(
    db: AsyncSession, role_id: uuid.UUID | str
) -> int:
    result = await db.execute(
        select(func.count(User.id)).where(User.role_id == role_id)
    )
    return result.scalar_one()


async def delete_role(
    db: AsyncSession,
    *,
    account_id: uuid.UUID | str,
    role_id: uuid.UUID | str,
) -> None:
    role = await _get_role_for_account(db, account_id, role_id)
    if role is None:
        raise RoleNotFoundError(f"Role não encontrada: {role_id}")
    if await _role_member_count(db, role.id) > 0:
        raise RoleInUseError("Role está em uso por um ou mais usuários.")
    await db.delete(role)
    await db.commit()


# ---------------------------------------------------------------------------
# Membros (escopados à account)
# ---------------------------------------------------------------------------
async def _get_member_for_account(
    db: AsyncSession, account_id: uuid.UUID | str, member_id: uuid.UUID | str
) -> User | None:
    result = await db.execute(
        select(User).where(
            User.id == member_id,
            User.account_id == account_id,
            User.role == UserRole.MEMBER.value,
        )
    )
    return result.scalar_one_or_none()


async def create_member(
    db: AsyncSession,
    *,
    account_id: uuid.UUID | str,
    email: str,
    password: str | None,
    role_id: uuid.UUID | str,
) -> User:
    if await _get_role_for_account(db, account_id, role_id) is None:
        raise RoleNotFoundError(f"Role não encontrada: {role_id}")

    existing = await get_users_by_email(db, email)
    # Não pode haver duas linhas do mesmo email nesta account.
    if any(str(u.account_id) == str(account_id) for u in existing):
        raise DuplicateEmailError(f"Email already registered: {email}")
    # Se o email já existe na plataforma (outra empresa), reaproveitamos a
    # senha da identidade — o convidado entra com a senha que já tem. Senha
    # nova só é exigida (e usada) quando o email é inédito.
    if existing:
        if any(u.role == UserRole.ADMIN.value for u in existing):
            raise DuplicateEmailError(f"Email already registered: {email}")
        password_hash = existing[0].password_hash
    else:
        if not password:
            raise PasswordRequiredError("Senha obrigatória para novo usuário.")
        password_hash = hash_password(password)

    member = User(
        email=email,
        password_hash=password_hash,
        role=UserRole.MEMBER.value,
        account_id=uuid.UUID(str(account_id)),
        role_id=uuid.UUID(str(role_id)),
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


async def list_members(
    db: AsyncSession, account_id: uuid.UUID | str
) -> list[tuple[User, str | None]]:
    result = await db.execute(
        select(User, AccountRole.name)
        .outerjoin(AccountRole, AccountRole.id == User.role_id)
        .where(
            User.account_id == account_id,
            User.role == UserRole.MEMBER.value,
        )
        .order_by(User.created_at.asc())
    )
    return [(row[0], row[1]) for row in result.all()]


async def update_member(
    db: AsyncSession,
    *,
    account_id: uuid.UUID | str,
    member_id: uuid.UUID | str,
    email: str | None = None,
    password: str | None = None,
    role_id: uuid.UUID | str | None = None,
) -> User:
    member = await _get_member_for_account(db, account_id, member_id)
    if member is None:
        raise MemberNotFoundError(f"Membro não encontrado: {member_id}")
    if role_id is not None:
        if await _get_role_for_account(db, account_id, role_id) is None:
            raise RoleNotFoundError(f"Role não encontrada: {role_id}")
        member.role_id = uuid.UUID(str(role_id))

    # Credencial (email/senha) só pode ser mexida pelo owner se o email for
    # exclusivo desta account. Se a identidade também participa de outras
    # empresas, a credencial é compartilhada — quem gere é a própria identidade.
    if email is not None or password is not None:
        shared = any(
            u.account_id != member.account_id
            for u in await get_users_by_email(db, member.email)
        )
        if shared:
            raise SharedIdentityError(
                "Usuário também pertence a outras empresas; "
                "a senha/email é gerida pelo próprio usuário."
            )

    if email is not None and email != member.email:
        if await get_users_by_email(db, email):
            raise DuplicateEmailError(f"Email already registered: {email}")
        member.email = email
    if password is not None:
        member.password_hash = hash_password(password)
    await db.commit()
    await db.refresh(member)
    return member


async def delete_member(
    db: AsyncSession,
    *,
    account_id: uuid.UUID | str,
    member_id: uuid.UUID | str,
) -> None:
    member = await _get_member_for_account(db, account_id, member_id)
    if member is None:
        raise MemberNotFoundError(f"Membro não encontrado: {member_id}")
    await db.delete(member)
    await db.commit()
