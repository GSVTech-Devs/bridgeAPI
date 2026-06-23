"""Serviço de alertas (Fase 6): dispara/resolve alertas com deduplicação e
listagem escopada por dono (admin vê tudo; cliente vê só os da própria conta).

Os gatilhos vivem nos domínios de origem (status/captcha/proxy) e chamam
``raise_alert``/``resolve_alerts``. As funções aqui não importam nada desses
domínios para evitar ciclos."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domains.alerts.models import Alert, AlertSeverity, AlertStatus, AlertType
from app.domains.alerts.schemas import AlertListResponse, AlertResponse
from app.domains.apis.models import ExternalAPI

_OPEN = (AlertStatus.ACTIVE.value, AlertStatus.ACKNOWLEDGED.value)


class AlertNotFoundError(Exception):
    pass


def _scope_clause(column, value):
    """Cláusula de igualdade que trata NULL corretamente (NULL = plataforma)."""
    return column.is_(None) if value is None else column == value


def to_response(alert: Alert, api_name: str | None = None) -> AlertResponse:
    return AlertResponse(
        id=alert.id,
        account_id=alert.account_id,
        api_id=alert.api_id,
        api_name=api_name,
        resource_id=alert.resource_id,
        type=alert.type,
        severity=alert.severity,
        status=alert.status,
        message=alert.message,
        context=alert.context,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
        resolved_at=alert.resolved_at,
    )


async def _find_open(
    db: AsyncSession, *, type_: str, account_id, api_id, resource_id
) -> Alert | None:
    result = await db.execute(
        select(Alert).where(
            Alert.type == type_,
            Alert.status.in_(_OPEN),
            _scope_clause(Alert.account_id, account_id),
            _scope_clause(Alert.api_id, api_id),
            _scope_clause(Alert.resource_id, resource_id),
        )
    )
    return result.scalars().first()


async def raise_alert(
    db: AsyncSession,
    *,
    type: AlertType,
    severity: AlertSeverity,
    message: str,
    account_id: uuid.UUID | None = None,
    api_id: uuid.UUID | None = None,
    resource_id: uuid.UUID | None = None,
    context: dict | None = None,
) -> Alert:
    """Cria um alerta ativo. Deduplicação: se já existe um alerta aberto
    (active/acknowledged) com o mesmo (conta, api, tipo, recurso), atualiza-o
    em vez de criar outro — evita spam quando a condição persiste."""
    existing = await _find_open(
        db, type_=type.value, account_id=account_id, api_id=api_id, resource_id=resource_id
    )
    now = datetime.now(timezone.utc)
    if existing is not None:
        existing.severity = severity.value
        existing.message = message
        existing.context = context
        existing.updated_at = now
        await db.commit()
        await db.refresh(existing)
        return existing

    alert = Alert(
        account_id=account_id,
        api_id=api_id,
        resource_id=resource_id,
        type=type.value,
        severity=severity.value,
        status=AlertStatus.ACTIVE.value,
        message=message,
        context=context,
        created_at=now,
        updated_at=now,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


async def resolve_alerts(
    db: AsyncSession,
    *,
    types: list[AlertType],
    account_id: uuid.UUID | None = None,
    api_id: uuid.UUID | None = None,
    resource_id: uuid.UUID | None = None,
) -> int:
    """Marca como resolvido todo alerta aberto que casa com o escopo. Retorna
    quantos foram resolvidos. Usado para auto-resolver quando a condição limpa."""
    result = await db.execute(
        select(Alert).where(
            Alert.type.in_([t.value for t in types]),
            Alert.status.in_(_OPEN),
            _scope_clause(Alert.account_id, account_id),
            _scope_clause(Alert.api_id, api_id),
            _scope_clause(Alert.resource_id, resource_id),
        )
    )
    now = datetime.now(timezone.utc)
    alerts = list(result.scalars().all())
    for a in alerts:
        a.status = AlertStatus.RESOLVED.value
        a.resolved_at = now
        a.updated_at = now
    if alerts:
        await db.commit()
    return len(alerts)


# --------------------------------------------------- gatilhos de alto nível
async def sync_api_status_alert(db: AsyncSession, api_id: uuid.UUID, to_status: str) -> None:
    """Status reportado mudou: abre api_down/api_degraded (escopo plataforma) ou
    resolve os abertos quando a API volta a um estado saudável."""
    if to_status == "down":
        await raise_alert(
            db, type=AlertType.API_DOWN, severity=AlertSeverity.CRITICAL,
            api_id=api_id, message="API reportou estado 'down'.",
        )
    elif to_status == "degraded":
        await raise_alert(
            db, type=AlertType.API_DEGRADED, severity=AlertSeverity.WARNING,
            api_id=api_id, message="API reportou estado 'degraded'.",
        )
    else:
        await resolve_alerts(
            db, types=[AlertType.API_DOWN, AlertType.API_DEGRADED], api_id=api_id
        )


async def sync_captcha_alert(
    db: AsyncSession, *, api_id: uuid.UUID, account_id: uuid.UUID | None,
    resource_id: uuid.UUID, name: str, status: str, balance_usd: float | None,
) -> None:
    """Avalia o estado de um provedor de captcha após um report e abre/resolve
    os alertas de saldo baixo e de falha conforme o caso."""
    threshold = settings.captcha_low_balance_threshold_usd
    if status == "failing":
        await raise_alert(
            db, type=AlertType.CAPTCHA_FAILING, severity=AlertSeverity.CRITICAL,
            account_id=account_id, api_id=api_id, resource_id=resource_id,
            message=f"Provedor de captcha '{name}' está falhando.",
        )
    else:
        await resolve_alerts(
            db, types=[AlertType.CAPTCHA_FAILING],
            account_id=account_id, api_id=api_id, resource_id=resource_id,
        )

    if balance_usd is not None and balance_usd < threshold:
        await raise_alert(
            db, type=AlertType.CAPTCHA_LOW_BALANCE, severity=AlertSeverity.WARNING,
            account_id=account_id, api_id=api_id, resource_id=resource_id,
            message=f"Saldo do captcha '{name}' abaixo de ${threshold:.2f} (atual: ${balance_usd:.2f}).",
            context={"balance_usd": balance_usd, "threshold": threshold},
        )
    elif balance_usd is not None:
        await resolve_alerts(
            db, types=[AlertType.CAPTCHA_LOW_BALANCE],
            account_id=account_id, api_id=api_id, resource_id=resource_id,
        )


async def sync_proxy_alert(
    db: AsyncSession, *, api_id: uuid.UUID, account_id: uuid.UUID | None,
    resource_id: uuid.UUID, name: str, status: str,
) -> None:
    """Abre/resolve o alerta de proxy falhando conforme o status reportado."""
    if status == "failing":
        await raise_alert(
            db, type=AlertType.PROXY_FAILING, severity=AlertSeverity.WARNING,
            account_id=account_id, api_id=api_id, resource_id=resource_id,
            message=f"Proxy '{name}' está falhando.",
        )
    else:
        await resolve_alerts(
            db, types=[AlertType.PROXY_FAILING],
            account_id=account_id, api_id=api_id, resource_id=resource_id,
        )


# --------------------------------------------------- leitura (admin/cliente)
async def _api_name_map(db: AsyncSession, api_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    ids = [i for i in api_ids if i is not None]
    if not ids:
        return {}
    result = await db.execute(
        select(ExternalAPI.id, ExternalAPI.name).where(ExternalAPI.id.in_(ids))
    )
    return {row.id: row.name for row in result.fetchall()}


def _visibility_clause(account_id: uuid.UUID | None, is_admin: bool):
    # admin vê tudo; cliente vê só os alertas da própria conta.
    return None if is_admin else (Alert.account_id == account_id)


async def list_alerts(
    db: AsyncSession,
    *,
    account_id: uuid.UUID | None,
    is_admin: bool,
    status: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> AlertListResponse:
    vis = _visibility_clause(account_id, is_admin)
    base = [vis] if vis is not None else []  # cláusula de visibilidade (admin vê tudo)
    conds = list(base)
    if status is not None:
        conds.append(Alert.status == status)

    total = (
        await db.execute(select(func.count()).select_from(Alert).where(*conds))
    ).scalar_one()
    # active_count ignora o filtro de status: conta só os abertos visíveis (badge do sino).
    active_count = (
        await db.execute(
            select(func.count())
            .select_from(Alert)
            .where(*base, Alert.status == AlertStatus.ACTIVE.value)
        )
    ).scalar_one()

    result = await db.execute(
        select(Alert)
        .where(*conds)
        .order_by(Alert.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    alerts = list(result.scalars().all())
    names = await _api_name_map(db, [a.api_id for a in alerts])
    items = [to_response(a, names.get(a.api_id)) for a in alerts]
    return AlertListResponse(items=items, total=total, active_count=active_count)


async def acknowledge_alert(
    db: AsyncSession, alert_id: str, *, account_id: uuid.UUID | None, is_admin: bool
) -> Alert:
    result = await db.execute(select(Alert).where(Alert.id == uuid.UUID(str(alert_id))))
    alert = result.scalar_one_or_none()
    if alert is None or (not is_admin and alert.account_id != account_id):
        raise AlertNotFoundError(f"Alert not found: {alert_id}")
    if alert.status == AlertStatus.ACTIVE.value:
        alert.status = AlertStatus.ACKNOWLEDGED.value
        alert.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(alert)
    return alert
