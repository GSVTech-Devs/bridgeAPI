from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

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
