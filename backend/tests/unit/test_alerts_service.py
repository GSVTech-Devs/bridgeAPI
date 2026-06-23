# Serviço de alertas (Fase 6): dedup, resolução, decisão dos gatilhos e escopo.
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domains.alerts import service as svc
from app.domains.alerts.models import Alert, AlertSeverity, AlertStatus, AlertType


def _db_with_first(value):
    """Mock de AsyncSession cujo execute() devolve .scalars().first() = value."""
    result = MagicMock()
    result.scalars.return_value.first.return_value = value
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    return db


def _db_with_all(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_raise_alert_creates_when_none_open() -> None:
    db = _db_with_first(None)
    api_id = uuid.uuid4()
    await svc.raise_alert(
        db, type=AlertType.API_DOWN, severity=AlertSeverity.CRITICAL,
        api_id=api_id, message="down",
    )
    added = db.add.call_args[0][0]
    assert isinstance(added, Alert)
    assert added.type == AlertType.API_DOWN.value
    assert added.severity == AlertSeverity.CRITICAL.value
    assert added.status == AlertStatus.ACTIVE.value
    assert added.api_id == api_id
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_raise_alert_dedups_existing_open() -> None:
    existing = Alert(
        type=AlertType.CAPTCHA_LOW_BALANCE.value, severity=AlertSeverity.WARNING.value,
        status=AlertStatus.ACTIVE.value, message="old",
    )
    db = _db_with_first(existing)
    await svc.raise_alert(
        db, type=AlertType.CAPTCHA_LOW_BALANCE, severity=AlertSeverity.WARNING,
        message="new message", context={"balance_usd": 1.0},
    )
    db.add.assert_not_called()  # não cria outro
    assert existing.message == "new message"
    assert existing.context == {"balance_usd": 1.0}
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_resolve_alerts_marks_resolved() -> None:
    a1 = Alert(type=AlertType.API_DOWN.value, status=AlertStatus.ACTIVE.value, message="x", severity="critical")
    a2 = Alert(type=AlertType.API_DEGRADED.value, status=AlertStatus.ACKNOWLEDGED.value, message="y", severity="warning")
    db = _db_with_all([a1, a2])
    n = await svc.resolve_alerts(
        db, types=[AlertType.API_DOWN, AlertType.API_DEGRADED], api_id=uuid.uuid4()
    )
    assert n == 2
    assert a1.status == AlertStatus.RESOLVED.value and a1.resolved_at is not None
    assert a2.status == AlertStatus.RESOLVED.value
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_sync_api_status_alert_down_raises() -> None:
    db = AsyncMock()
    api_id = uuid.uuid4()
    with patch.object(svc, "raise_alert", new=AsyncMock()) as raise_, patch.object(
        svc, "resolve_alerts", new=AsyncMock()
    ) as resolve_:
        await svc.sync_api_status_alert(db, api_id, "down")
    assert raise_.await_args.kwargs["type"] == AlertType.API_DOWN
    resolve_.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_api_status_alert_healthy_resolves() -> None:
    db = AsyncMock()
    with patch.object(svc, "raise_alert", new=AsyncMock()) as raise_, patch.object(
        svc, "resolve_alerts", new=AsyncMock()
    ) as resolve_:
        await svc.sync_api_status_alert(db, uuid.uuid4(), "healthy")
    raise_.assert_not_awaited()
    assert resolve_.await_args.kwargs["types"] == [AlertType.API_DOWN, AlertType.API_DEGRADED]


@pytest.mark.asyncio
async def test_sync_captcha_alert_low_balance_raises_scoped() -> None:
    db = AsyncMock()
    account = uuid.uuid4()
    with patch.object(svc, "raise_alert", new=AsyncMock()) as raise_, patch.object(
        svc, "resolve_alerts", new=AsyncMock()
    ), patch.object(svc.settings, "captcha_low_balance_threshold_usd", 5.0):
        await svc.sync_captcha_alert(
            db, api_id=uuid.uuid4(), account_id=account, resource_id=uuid.uuid4(),
            name="2captcha", status="active", balance_usd=1.5,
        )
    kinds = [c.kwargs["type"] for c in raise_.await_args_list]
    assert AlertType.CAPTCHA_LOW_BALANCE in kinds
    low = next(c for c in raise_.await_args_list if c.kwargs["type"] == AlertType.CAPTCHA_LOW_BALANCE)
    assert low.kwargs["account_id"] == account  # escopado ao dono


@pytest.mark.asyncio
async def test_sync_captcha_alert_healthy_resolves() -> None:
    db = AsyncMock()
    with patch.object(svc, "raise_alert", new=AsyncMock()) as raise_, patch.object(
        svc, "resolve_alerts", new=AsyncMock()
    ) as resolve_, patch.object(svc.settings, "captcha_low_balance_threshold_usd", 5.0):
        await svc.sync_captcha_alert(
            db, api_id=uuid.uuid4(), account_id=None, resource_id=uuid.uuid4(),
            name="2captcha", status="active", balance_usd=50.0,
        )
    raise_.assert_not_awaited()
    resolved_types = [c.kwargs["types"] for c in resolve_.await_args_list]
    assert [AlertType.CAPTCHA_FAILING] in resolved_types
    assert [AlertType.CAPTCHA_LOW_BALANCE] in resolved_types


@pytest.mark.asyncio
async def test_acknowledge_alert_scope_blocks_other_account() -> None:
    other = Alert(status=AlertStatus.ACTIVE.value, message="x", severity="warning", type="t")
    other.account_id = uuid.uuid4()
    result = MagicMock()
    result.scalar_one_or_none.return_value = other
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    with pytest.raises(svc.AlertNotFoundError):
        await svc.acknowledge_alert(db, str(uuid.uuid4()), account_id=uuid.uuid4(), is_admin=False)


@pytest.mark.asyncio
async def test_acknowledge_alert_sets_acknowledged() -> None:
    alert = Alert(status=AlertStatus.ACTIVE.value, message="x", severity="warning", type="t")
    alert.account_id = None
    result = MagicMock()
    result.scalar_one_or_none.return_value = alert
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    out = await svc.acknowledge_alert(db, str(uuid.uuid4()), account_id=None, is_admin=True)
    assert out.status == AlertStatus.ACKNOWLEDGED.value
    db.commit.assert_awaited()
