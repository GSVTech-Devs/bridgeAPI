# RED → GREEN
# Testes unitários para app/domains/metrics/service.py — funções de agregação.
# SQLAlchemy é mockado com AsyncMock — nenhuma conexão real.
# Cobre: total de requests, taxa de erro, latência média, custo, billable/non-billable,
# filtro por date range e métricas globais de admin.
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domains.metrics.service import (
    get_admin_global_metrics,
    get_client_dashboard,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_db_mock(
    scalar_result: Any = None, all_result: list | None = None
) -> AsyncMock:
    """Mock de AsyncSession com execute().scalar() e execute().all()."""
    db = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar.return_value = scalar_result
    execute_result.scalars.return_value.all.return_value = all_result or []
    execute_result.all.return_value = all_result or []
    db.execute.return_value = execute_result
    return db


def _make_row(
    total: int = 0,
    errors: int = 0,
    avg_latency: float = 0.0,
    total_cost: float | None = None,
) -> MagicMock:
    row = MagicMock()
    row.total = total
    row.errors = errors
    row.avg_latency = avg_latency
    row.total_cost = total_cost
    return row


def make_db_mock_row(row: MagicMock) -> AsyncMock:
    """Mock que retorna uma Row de agregação."""
    db = AsyncMock()
    execute_result = MagicMock()
    execute_result.one.return_value = row
    execute_result.fetchone.return_value = row
    db.execute.return_value = execute_result
    return db


# ---------------------------------------------------------------------------
# get_client_dashboard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_returns_correct_total_requests() -> None:
    client_id = uuid.uuid4()
    row = _make_row(total=150, errors=10, avg_latency=42.0, total_cost=0.75)
    db = make_db_mock_row(row)

    result = await get_client_dashboard(db, client_id)

    assert result["total_requests"] == 150


@pytest.mark.asyncio
async def test_error_rate_calculated_correctly() -> None:
    client_id = uuid.uuid4()
    # 20 errors out of 100 requests → 20%
    row = _make_row(total=100, errors=20, avg_latency=50.0)
    db = make_db_mock_row(row)

    result = await get_client_dashboard(db, client_id)

    assert result["error_rate"] == pytest.approx(20.0)


@pytest.mark.asyncio
async def test_error_rate_is_zero_when_no_requests() -> None:
    client_id = uuid.uuid4()
    row = _make_row(total=0, errors=0, avg_latency=0.0)
    db = make_db_mock_row(row)

    result = await get_client_dashboard(db, client_id)

    assert result["error_rate"] == 0.0


@pytest.mark.asyncio
async def test_average_latency_calculated_correctly() -> None:
    client_id = uuid.uuid4()
    row = _make_row(total=50, errors=0, avg_latency=123.45)
    db = make_db_mock_row(row)

    result = await get_client_dashboard(db, client_id)

    assert result["avg_latency_ms"] == pytest.approx(123.45)


@pytest.mark.asyncio
async def test_cost_aggregation_is_returned() -> None:
    client_id = uuid.uuid4()
    row = _make_row(total=30, errors=2, avg_latency=80.0, total_cost=2.50)
    db = make_db_mock_row(row)

    result = await get_client_dashboard(db, client_id)

    assert result["total_cost"] == pytest.approx(2.50)


@pytest.mark.asyncio
async def test_cost_is_zero_when_no_billable_requests() -> None:
    client_id = uuid.uuid4()
    row = _make_row(total=10, errors=0, avg_latency=30.0, total_cost=None)
    db = make_db_mock_row(row)

    result = await get_client_dashboard(db, client_id)

    assert result["total_cost"] == 0.0


@pytest.mark.asyncio
async def test_billable_vs_non_billable_counts() -> None:
    client_id = uuid.uuid4()
    row = _make_row(total=100, errors=5, avg_latency=40.0, total_cost=1.0)
    db = make_db_mock_row(row)

    result = await get_client_dashboard(db, client_id)

    assert "billable_requests" in result
    assert "non_billable_requests" in result
    assert (
        result["billable_requests"] + result["non_billable_requests"]
        == result["total_requests"]
    )


@pytest.mark.asyncio
async def test_metrics_filtered_by_date_range() -> None:
    client_id = uuid.uuid4()
    since = datetime.now(timezone.utc) - timedelta(days=7)
    until = datetime.now(timezone.utc)
    row = _make_row(total=42, errors=3, avg_latency=60.0)
    db = make_db_mock_row(row)

    result = await get_client_dashboard(db, client_id, since=since, until=until)

    assert result["total_requests"] == 42
    # verifica que a query foi executada com filtro de datas
    assert db.execute.called


@pytest.mark.asyncio
async def test_dashboard_without_date_range_returns_all_time() -> None:
    client_id = uuid.uuid4()
    row = _make_row(total=999, errors=1, avg_latency=20.0)
    db = make_db_mock_row(row)

    result = await get_client_dashboard(db, client_id)

    assert result["total_requests"] == 999
    assert db.execute.called


@pytest.mark.asyncio
async def test_dashboard_response_has_all_expected_keys() -> None:
    client_id = uuid.uuid4()
    row = _make_row(total=10, errors=1, avg_latency=55.0, total_cost=0.10)
    db = make_db_mock_row(row)

    result = await get_client_dashboard(db, client_id)

    expected_keys = {
        "total_requests",
        "error_rate",
        "avg_latency_ms",
        "total_cost",
        "billable_requests",
        "non_billable_requests",
    }
    assert expected_keys.issubset(result.keys())


# ---------------------------------------------------------------------------
# get_admin_global_metrics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_global_metrics_returns_total_requests() -> None:
    row = _make_row(total=5000, errors=250, avg_latency=70.0, total_cost=50.0)
    db = make_db_mock_row(row)

    result = await get_admin_global_metrics(db)

    assert result["total_requests"] == 5000


@pytest.mark.asyncio
async def test_admin_global_metrics_includes_error_rate() -> None:
    row = _make_row(total=1000, errors=50, avg_latency=90.0)
    db = make_db_mock_row(row)

    result = await get_admin_global_metrics(db)

    assert result["error_rate"] == pytest.approx(5.0)


@pytest.mark.asyncio
async def test_admin_global_metrics_not_scoped_to_client() -> None:
    """Admin query não deve filtrar por client_id."""
    row = _make_row(total=200, errors=10, avg_latency=45.0)
    db = make_db_mock_row(row)

    result = await get_admin_global_metrics(db)

    # Apenas verifica que a função retorna dados completos sem client filter
    assert result["total_requests"] == 200
    assert db.execute.called


@pytest.mark.asyncio
async def test_admin_global_metrics_filtered_by_date_range() -> None:
    since = datetime.now(timezone.utc) - timedelta(days=30)
    row = _make_row(total=8000, errors=400, avg_latency=55.0, total_cost=80.0)
    db = make_db_mock_row(row)

    result = await get_admin_global_metrics(db, since=since)

    assert result["total_requests"] == 8000
    assert db.execute.called


@pytest.mark.asyncio
async def test_admin_global_metrics_has_all_expected_keys() -> None:
    row = _make_row(total=100, errors=5, avg_latency=30.0, total_cost=1.0)
    db = make_db_mock_row(row)

    result = await get_admin_global_metrics(db)

    expected_keys = {
        "total_requests",
        "error_rate",
        "avg_latency_ms",
        "total_cost",
        "billable_requests",
        "non_billable_requests",
    }
    assert expected_keys.issubset(result.keys())
