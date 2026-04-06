from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.metrics.models import RequestMetric


async def record_metric(
    db: AsyncSession,
    client_id: uuid.UUID,
    api_id: uuid.UUID,
    key_id: uuid.UUID,
    path: str,
    method: str,
    status_code: int,
    latency_ms: float,
    cost: Optional[float],
) -> RequestMetric:
    metric = RequestMetric(
        client_id=client_id,
        api_id=api_id,
        key_id=key_id,
        path=path,
        method=method,
        status_code=status_code,
        latency_ms=latency_ms,
        cost=cost,
        created_at=datetime.now(timezone.utc),
    )
    db.add(metric)
    await db.commit()
    return metric


def _build_aggregation_query(
    client_id: Optional[uuid.UUID] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> Any:
    """Constrói query de agregação com filtros opcionais."""
    stmt = select(
        func.count(RequestMetric.id).label("total"),
        func.sum(func.cast(RequestMetric.status_code >= 500, Integer)).label(
            "errors"
        ),
        func.avg(RequestMetric.latency_ms).label("avg_latency"),
        func.sum(RequestMetric.cost).label("total_cost"),
        func.sum(func.cast(RequestMetric.cost.isnot(None), Integer)).label(
            "billable"
        ),
    )
    if client_id is not None:
        stmt = stmt.where(RequestMetric.client_id == client_id)
    if since is not None:
        stmt = stmt.where(RequestMetric.created_at >= since)
    if until is not None:
        stmt = stmt.where(RequestMetric.created_at <= until)
    return stmt


def _row_to_dict(row: Any) -> dict[str, Any]:
    total = row.total or 0
    errors = row.errors or 0
    avg_latency = float(row.avg_latency or 0.0)
    total_cost = float(row.total_cost) if row.total_cost is not None else 0.0
    billable = int(row.billable or 0)
    non_billable = total - billable
    error_rate = (errors / total) if total > 0 else 0.0
    return {
        "total_requests": total,
        "error_rate": round(error_rate, 4),
        "avg_latency_ms": round(avg_latency, 4),
        "total_cost": total_cost,
        "billable_requests": billable,
        "non_billable_requests": non_billable,
    }


async def get_client_dashboard(
    db: AsyncSession,
    client_id: uuid.UUID,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> dict[str, Any]:
    """Retorna métricas agregadas para um cliente específico."""
    stmt = _build_aggregation_query(client_id=client_id, since=since, until=until)
    result = await db.execute(stmt)
    row = result.fetchone()
    return _row_to_dict(row)


async def get_admin_global_metrics(
    db: AsyncSession,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> dict[str, Any]:
    """Retorna métricas globais de todas as APIs (acesso admin)."""
    stmt = _build_aggregation_query(since=since, until=until)
    result = await db.execute(stmt)
    row = result.fetchone()
    return _row_to_dict(row)
