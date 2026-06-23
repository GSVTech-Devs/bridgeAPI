from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    TIMEOUT = "timeout"


class ProxyJob(Base):
    """Consulta que excedeu o limite síncrono e virou job assíncrono. O resultado
    é entregue por polling (`GET /jobs/{id}`) — SSE/webhook na 5b."""

    __tablename__ = "proxy_jobs"
    __table_args__ = (
        # Idempotência: uma chave por conta mapeia para um único job.
        UniqueConstraint("account_id", "idempotency_key", name="uq_proxy_jobs_idem"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    api_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_apis.id", ondelete="CASCADE"), index=True
    )
    key_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.RUNNING, index=True)
    # Snapshot sanitizado da requisição (sem credenciais) — base p/ replay/debug.
    request_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    result_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
