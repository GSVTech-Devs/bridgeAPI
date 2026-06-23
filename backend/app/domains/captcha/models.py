from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CaptchaStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILING = "failing"


class CaptchaProvider(Base):
    """Provedor de captcha de UMA API. Pertence ao admin (``account_id`` NULL) ou
    a um cliente. Vários por API, com prioridade/failover. ``balance_usd`` e
    ``status``/``last_error`` alimentam o monitoramento (e a SDK pula provedores
    sem saldo)."""

    __tablename__ = "captcha_providers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    api_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_apis.id", ondelete="CASCADE"), index=True
    )
    # NULL = provedor do admin (default da API); preenchido = provedor do cliente.
    account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    provider: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    api_key_encrypted: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    balance_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    status: Mapped[str] = mapped_column(
        String(20), default=CaptchaStatus.ACTIVE, index=True
    )
    last_error: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    last_error_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
