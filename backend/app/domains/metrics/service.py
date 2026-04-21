from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.apis.models import ExternalAPI
from app.domains.clients.models import Client
from app.domains.keys.models import APIKey
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
        func.sum(func.cast(RequestMetric.status_code != 200, Integer)).label("errors"),
        func.avg(RequestMetric.latency_ms).label("avg_latency"),
        func.sum(RequestMetric.cost).label("total_cost"),
        func.sum(func.cast(RequestMetric.cost.isnot(None), Integer)).label("billable"),
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
    error_rate = (errors / total * 100) if total > 0 else 0.0
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


async def get_usage_by_client_and_api(
    db: AsyncSession,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    """Retorna total de requisições e custo acumulado por cliente + API."""
    stmt = (
        select(
            Client.id.label("client_id"),
            Client.name.label("client_name"),
            Client.email.label("client_email"),
            ExternalAPI.id.label("api_id"),
            ExternalAPI.name.label("api_name"),
            func.count(RequestMetric.id).label("total_requests"),
            func.sum(RequestMetric.cost).label("total_cost"),
        )
        .join(Client, RequestMetric.client_id == Client.id)
        .join(ExternalAPI, RequestMetric.api_id == ExternalAPI.id)
        .group_by(Client.id, Client.name, Client.email, ExternalAPI.id, ExternalAPI.name)
        .order_by(Client.name, ExternalAPI.name)
    )
    if since is not None:
        stmt = stmt.where(RequestMetric.created_at >= since)
    if until is not None:
        stmt = stmt.where(RequestMetric.created_at <= until)
    result = await db.execute(stmt)
    rows = result.fetchall()
    return [
        {
            "client_id": str(row.client_id),
            "client_name": row.client_name,
            "client_email": row.client_email,
            "api_id": str(row.api_id),
            "api_name": row.api_name,
            "total_requests": row.total_requests or 0,
            "total_cost": float(row.total_cost) if row.total_cost is not None else 0.0,
        }
        for row in rows
    ]


async def get_clients_usage_summary(
    db: AsyncSession,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    """Total de requisições, erros e custo por cliente (visão resumida)."""
    stmt = (
        select(
            Client.id.label("client_id"),
            Client.name.label("client_name"),
            Client.email.label("client_email"),
            func.count(RequestMetric.id).label("total_requests"),
            func.sum(func.cast(RequestMetric.status_code != 200, Integer)).label("error_count"),
            func.sum(RequestMetric.cost).label("total_cost"),
        )
        .join(Client, RequestMetric.client_id == Client.id)
        .group_by(Client.id, Client.name, Client.email)
        .order_by(func.sum(RequestMetric.cost).desc().nulls_last())
    )
    if since is not None:
        stmt = stmt.where(RequestMetric.created_at >= since)
    if until is not None:
        stmt = stmt.where(RequestMetric.created_at <= until)
    result = await db.execute(stmt)
    rows = result.fetchall()
    return [
        {
            "client_id": str(row.client_id),
            "client_name": row.client_name,
            "client_email": row.client_email,
            "total_requests": row.total_requests or 0,
            "error_count": int(row.error_count or 0),
            "success_count": (row.total_requests or 0) - int(row.error_count or 0),
            "total_cost": float(row.total_cost) if row.total_cost is not None else 0.0,
        }
        for row in rows
    ]


async def get_client_api_detail(
    db: AsyncSession,
    client_id: str,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    """Detalhe de uso por API para um cliente: requests, erros, custo."""
    stmt = (
        select(
            ExternalAPI.id.label("api_id"),
            ExternalAPI.name.label("api_name"),
            func.count(RequestMetric.id).label("total_requests"),
            func.sum(func.cast(RequestMetric.status_code != 200, Integer)).label("error_count"),
            func.sum(func.cast(RequestMetric.status_code == 200, Integer)).label("success_count"),
            func.sum(RequestMetric.cost).label("total_cost"),
        )
        .join(ExternalAPI, RequestMetric.api_id == ExternalAPI.id)
        .where(RequestMetric.client_id == client_id)
        .group_by(ExternalAPI.id, ExternalAPI.name)
        .order_by(ExternalAPI.name)
    )
    if since is not None:
        stmt = stmt.where(RequestMetric.created_at >= since)
    if until is not None:
        stmt = stmt.where(RequestMetric.created_at <= until)
    result = await db.execute(stmt)
    rows = result.fetchall()
    return [
        {
            "api_id": str(row.api_id),
            "api_name": row.api_name,
            "total_requests": row.total_requests or 0,
            "error_count": int(row.error_count or 0),
            "success_count": int(row.success_count or 0),
            "total_cost": float(row.total_cost) if row.total_cost is not None else 0.0,
        }
        for row in rows
    ]


async def get_client_status_codes(
    db: AsyncSession,
    client_id: uuid.UUID,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    top_n: int = 5,
) -> list[dict[str, Any]]:
    from collections import defaultdict
    stmt = (
        select(
            ExternalAPI.id.label("api_id"),
            ExternalAPI.name.label("api_name"),
            RequestMetric.status_code,
            func.count(RequestMetric.id).label("count"),
        )
        .join(ExternalAPI, RequestMetric.api_id == ExternalAPI.id)
        .where(RequestMetric.client_id == client_id)
        .group_by(ExternalAPI.id, ExternalAPI.name, RequestMetric.status_code)
        .order_by(ExternalAPI.name, func.count(RequestMetric.id).desc())
    )
    if since is not None:
        stmt = stmt.where(RequestMetric.created_at >= since)
    if until is not None:
        stmt = stmt.where(RequestMetric.created_at <= until)
    result = await db.execute(stmt)
    rows = result.fetchall()
    api_codes: dict[str, list] = defaultdict(list)
    for row in rows:
        key = str(row.api_id)
        if len(api_codes[key]) < top_n:
            api_codes[key].append({
                "api_id": str(row.api_id),
                "api_name": row.api_name,
                "status_code": row.status_code,
                "count": row.count,
            })
    return [item for items in api_codes.values() for item in items]


async def get_client_requests_by_key(
    db: AsyncSession,
    client_id: uuid.UUID,
    api_id: Optional[uuid.UUID] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    """Requests agrupados por API key para um cliente."""
    stmt = (
        select(
            APIKey.id.label("key_id"),
            APIKey.name.label("key_name"),
            APIKey.key_prefix,
            func.count(RequestMetric.id).label("total_requests"),
        )
        .join(APIKey, RequestMetric.key_id == APIKey.id)
        .where(RequestMetric.client_id == client_id)
        .group_by(APIKey.id, APIKey.name, APIKey.key_prefix)
        .order_by(func.count(RequestMetric.id).desc())
    )
    if api_id is not None:
        stmt = stmt.where(RequestMetric.api_id == api_id)
    if since is not None:
        stmt = stmt.where(RequestMetric.created_at >= since)
    if until is not None:
        stmt = stmt.where(RequestMetric.created_at <= until)
    result = await db.execute(stmt)
    rows = result.fetchall()
    return [
        {
            "key_id": str(row.key_id),
            "key_name": row.key_name,
            "key_prefix": row.key_prefix,
            "total_requests": row.total_requests or 0,
        }
        for row in rows
    ]


async def get_metrics_by_api(
    db: AsyncSession,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    """Retorna métricas por API para breakdown no painel admin."""
    stmt = (
        select(
            ExternalAPI.id.label("api_id"),
            ExternalAPI.name.label("api_name"),
            func.count(RequestMetric.id).label("total"),
            func.sum(func.cast(RequestMetric.status_code != 200, Integer)).label("errors"),
        )
        .join(ExternalAPI, RequestMetric.api_id == ExternalAPI.id)
        .group_by(ExternalAPI.id, ExternalAPI.name)
    )
    if since is not None:
        stmt = stmt.where(RequestMetric.created_at >= since)
    if until is not None:
        stmt = stmt.where(RequestMetric.created_at <= until)
    result = await db.execute(stmt)
    rows = result.fetchall()
    return [
        {
            "api_id": str(row.api_id),
            "api_name": row.api_name,
            "total_requests": row.total or 0,
            "error_rate": round((row.errors or 0) / (row.total or 1) * 100, 2),
        }
        for row in rows
    ]
