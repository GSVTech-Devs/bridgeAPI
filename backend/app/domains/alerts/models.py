from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AlertType(str, Enum):
    API_DOWN = "api_down"
    API_DEGRADED = "api_degraded"
    CAPTCHA_LOW_BALANCE = "captcha_low_balance"
    CAPTCHA_FAILING = "captcha_failing"
    PROXY_FAILING = "proxy_failing"


class AlertSeverity(str, Enum):
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class Alert(Base):
    """Alerta in-app (Fase 6). Escopo por dono: ``account_id`` NULL = alerta da
    plataforma (só admin vê); preenchido = alerta do cliente que gerencia o
    próprio recurso (proxy/captcha). O admin vê todos; o cliente vê só os seus."""

    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    api_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("external_apis.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Recurso que originou o alerta (proxy/captcha), quando aplicável.
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)
    type: Mapped[str] = mapped_column(String(40), index=True)
    severity: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(
        String(20), default=AlertStatus.ACTIVE.value, index=True
    )
    message: Mapped[str] = mapped_column(Text)
    context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
