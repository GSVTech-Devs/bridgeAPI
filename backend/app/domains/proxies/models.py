from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProxyOwnership(str, Enum):
    PLATFORM = "platform"   # proxy do admin/plataforma
    CLIENT = "client"       # proxy do cliente


class ProxyType(str, Enum):
    DATACENTER = "datacenter"
    RESIDENTIAL = "residential"
    MOBILE = "mobile"


class ProxyScheme(str, Enum):
    HTTP = "http"
    HTTPS = "https"
    SOCKS5 = "socks5"


class ProxyRotation(str, Enum):
    STICKY = "sticky"
    ROTATING = "rotating"


class ProxyStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILING = "failing"


class Proxy(Base):
    """Proxy de UMA API. Pertence ao admin (``account_id`` NULL) ou a um cliente
    (``account_id`` preenchido). Uma API pode ter vários — com prioridade e
    failover. ``status``/``last_error`` alimentam o monitoramento."""

    __tablename__ = "proxies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    api_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_apis.id", ondelete="CASCADE"), index=True
    )
    # NULL = proxy do admin (default da API); preenchido = proxy do cliente.
    account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    provider: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ownership: Mapped[str] = mapped_column(String(20), default=ProxyOwnership.PLATFORM)
    type: Mapped[str] = mapped_column(String(20), default=ProxyType.DATACENTER)
    scheme: Mapped[str] = mapped_column(String(10), default=ProxyScheme.HTTP)
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer)
    username_encrypted: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    password_encrypted: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    rotation: Mapped[str] = mapped_column(String(20), default=ProxyRotation.STICKY)
    session_ttl_s: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=ProxyStatus.ACTIVE, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, default=100)
    last_error: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    last_error_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
