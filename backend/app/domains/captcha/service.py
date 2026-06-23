from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_value, encrypt_value
from app.domains.apis.models import ExternalAPI
from app.domains.apis.service import get_api_by_id
from app.domains.captcha.models import CaptchaProvider, CaptchaStatus
from app.domains.captcha.schemas import (
    CaptchaConfigItem,
    CaptchaConfigResponse,
    CaptchaMonitorItem,
    CaptchaResponse,
)
from app.domains.permissions.service import get_permission

# Mesma sentinela do proxy: "sem filtro de dono" vs admin (None) vs cliente (UUID).
_ANY_ACCOUNT = object()


class CaptchaNotFoundError(Exception):
    pass


# --------------------------------------------------------------------- helpers
def to_response(c: CaptchaProvider) -> CaptchaResponse:
    return CaptchaResponse(
        id=c.id,
        api_id=c.api_id,
        account_id=c.account_id,
        name=c.name,
        provider=c.provider,
        has_api_key=c.api_key_encrypted is not None,
        balance_usd=c.balance_usd,
        priority=c.priority,
        status=c.status,
        last_error=c.last_error,
        last_error_at=c.last_error_at,
        created_at=c.created_at,
    )


def _account_clause(account_id):
    if account_id is _ANY_ACCOUNT:
        return None
    if account_id is None:
        return CaptchaProvider.account_id.is_(None)
    return CaptchaProvider.account_id == uuid.UUID(str(account_id))


# --------------------------------------------------------------------- CRUD
async def create_captcha(db: AsyncSession, api_id: str, data, account_id=None) -> CaptchaProvider:
    await get_api_by_id(db, api_id)  # valida a API (404 se não existe)
    captcha = CaptchaProvider(
        api_id=uuid.UUID(str(api_id)),
        account_id=uuid.UUID(str(account_id)) if account_id is not None else None,
        name=data.name,
        provider=data.provider,
        api_key_encrypted=encrypt_value(data.api_key) if data.api_key else None,
        balance_usd=data.balance_usd,
        priority=data.priority,
    )
    db.add(captcha)
    await db.commit()
    await db.refresh(captcha)
    return captcha


async def list_api_captchas(
    db: AsyncSession, api_id: str, account_id=_ANY_ACCOUNT
) -> list[CaptchaProvider]:
    stmt = (
        select(CaptchaProvider)
        .where(CaptchaProvider.api_id == uuid.UUID(str(api_id)))
        .order_by(CaptchaProvider.priority, CaptchaProvider.name)
    )
    clause = _account_clause(account_id)
    if clause is not None:
        stmt = stmt.where(clause)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_captcha(db: AsyncSession, captcha_id: str) -> CaptchaProvider:
    result = await db.execute(
        select(CaptchaProvider).where(CaptchaProvider.id == uuid.UUID(str(captcha_id)))
    )
    captcha = result.scalar_one_or_none()
    if captcha is None:
        raise CaptchaNotFoundError(f"Captcha provider not found: {captcha_id}")
    return captcha


async def get_scoped_captcha(
    db: AsyncSession, captcha_id: str, api_id: str, account_id=_ANY_ACCOUNT
) -> CaptchaProvider:
    captcha = await get_captcha(db, captcha_id)
    if captcha.api_id != uuid.UUID(str(api_id)):
        raise CaptchaNotFoundError(f"Captcha provider not found: {captcha_id}")
    if account_id is not _ANY_ACCOUNT:
        want = uuid.UUID(str(account_id)) if account_id is not None else None
        if captcha.account_id != want:
            raise CaptchaNotFoundError(f"Captcha provider not found: {captcha_id}")
    return captcha


async def update_captcha(db: AsyncSession, captcha: CaptchaProvider, data) -> CaptchaProvider:
    for field in ("name", "provider", "balance_usd", "priority"):
        value = getattr(data, field)
        if value is not None:
            setattr(captcha, field, value)
    if data.status is not None:
        captcha.status = data.status.value
    if data.api_key is not None:
        captcha.api_key_encrypted = encrypt_value(data.api_key)

    # Reativar manualmente limpa o último erro.
    if data.status is not None and data.status == CaptchaStatus.ACTIVE:
        captcha.last_error = None
        captcha.last_error_at = None

    await db.commit()
    await db.refresh(captcha)
    return captcha


async def delete_captcha(db: AsyncSession, captcha: CaptchaProvider) -> None:
    await db.delete(captcha)
    await db.commit()


# --------------------------------------------------- resolução p/ a SDK
async def resolve_owner_for_request(db: AsyncSession, api: ExternalAPI, client_id=None):
    """Dono dos provedores a usar na chamada: o cliente (se a permissão dele marca
    ``captcha_managed_by_client``) — senão o admin (None)."""
    if client_id is None:
        return None
    perm = await get_permission(db, str(client_id), str(api.id))
    if perm is not None and perm.captcha_managed_by_client:
        return uuid.UUID(str(client_id))
    return None


async def _active_captchas(db: AsyncSession, api_id, owner) -> list[CaptchaProvider]:
    clause = (
        CaptchaProvider.account_id.is_(None)
        if owner is None
        else CaptchaProvider.account_id == owner
    )
    result = await db.execute(
        select(CaptchaProvider)
        .where(
            CaptchaProvider.api_id == api_id,
            CaptchaProvider.status == CaptchaStatus.ACTIVE.value,
            clause,
        )
        .order_by(CaptchaProvider.priority, CaptchaProvider.name)
    )
    return list(result.scalars().all())


async def get_captcha_config_for_api(
    db: AsyncSession, api: ExternalAPI, client_id=None
) -> CaptchaConfigResponse:
    """Provedores ativos a usar nesta chamada (resolvidos por dono), com a chave
    descriptografada e o saldo, por prioridade. Vazio se a API não usa captcha."""
    if not api.uses_captcha:
        return CaptchaConfigResponse(providers=[])
    owner = await resolve_owner_for_request(db, api, client_id)
    providers = await _active_captchas(db, api.id, owner)
    items = [
        CaptchaConfigItem(
            id=c.id,
            name=c.name,
            provider=c.provider,
            api_key=decrypt_value(c.api_key_encrypted) if c.api_key_encrypted else None,
            balance_usd=c.balance_usd,
            priority=c.priority,
        )
        for c in providers
    ]
    return CaptchaConfigResponse(providers=items)


async def report_captcha_failure(
    db: AsyncSession, api: ExternalAPI, data, client_id=None
) -> CaptchaProvider:
    """Marca um provedor como failing/inactive e/ou atualiza o saldo reportado.
    O provedor precisa ser desta API e do dono resolvido para a chamada."""
    owner = await resolve_owner_for_request(db, api, client_id)
    captcha = await get_captcha(db, str(data.provider_id))
    if captcha.api_id != api.id or captcha.account_id != owner:
        raise CaptchaNotFoundError("Captcha provider not in this API/owner scope")

    captcha.status = data.status.value
    captcha.last_error = data.message or data.error_code
    captcha.last_error_at = datetime.now(timezone.utc)
    if data.balance_usd is not None:
        captcha.balance_usd = data.balance_usd
    await db.commit()
    await db.refresh(captcha)
    return captcha


# ------------------------------------------------------ monitoramento agregado
async def monitor_captchas(db: AsyncSession) -> list[CaptchaMonitorItem]:
    result = await db.execute(
        select(CaptchaProvider, ExternalAPI.name)
        .join(ExternalAPI, ExternalAPI.id == CaptchaProvider.api_id)
        .order_by(ExternalAPI.name, CaptchaProvider.priority, CaptchaProvider.name)
    )
    return [
        CaptchaMonitorItem(
            id=c.id,
            api_id=c.api_id,
            api_name=api_name,
            account_id=c.account_id,
            name=c.name,
            provider=c.provider,
            balance_usd=c.balance_usd,
            status=c.status,
            priority=c.priority,
            last_error=c.last_error,
            last_error_at=c.last_error_at,
        )
        for c, api_name in result.all()
    ]
