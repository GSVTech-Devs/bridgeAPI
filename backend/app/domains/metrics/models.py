from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RequestMetric(Base):
    __tablename__ = "request_metrics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    # Nullable: a FK usa ON DELETE SET NULL para preservar o histórico quando a
    # API é deletada (o vínculo é desfeito, a linha permanece).
    api_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("external_apis.id"), index=True, nullable=True
    )
    key_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("api_keys.id"), index=True)
    path: Mapped[str] = mapped_column(String(2048))
    method: Mapped[str] = mapped_column(String(10))
    status_code: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[float] = mapped_column(Float)
    cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
