from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class APIAuthType(str, Enum):
    NONE = "none"
    API_KEY = "api_key"
    BEARER = "bearer"
    BASIC = "basic"


class APIStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class HTTPMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class ExternalAPI(Base):
    __tablename__ = "external_apis"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    slug: Mapped[Optional[str]] = mapped_column(String(200), unique=True, index=True, nullable=True)
    base_url: Mapped[str] = mapped_column(String(2048))
    master_key_encrypted: Mapped[Optional[str]] = mapped_column(
        String(2048), nullable=True
    )
    url_template: Mapped[Optional[str]] = mapped_column(String(4096), nullable=True)
    cost_per_query: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Token de serviço (≠ chave de cliente) com que a própria API se autentica
    # para enviar logs estruturados via POST /ingest/logs. Gerado sob demanda.
    service_token_prefix: Mapped[Optional[str]] = mapped_column(
        String(32), unique=True, index=True, nullable=True
    )
    service_token_hash: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    # Esta API usa proxy? Nem toda usa. Quando True, a lista de proxies vive em
    # `proxies` (do admin e/ou do cliente, conforme a permissão).
    uses_proxy: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    auth_type: Mapped[str] = mapped_column(String(20), default=APIAuthType.NONE)
    status: Mapped[str] = mapped_column(
        String(20), default=APIStatus.ACTIVE, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Endpoint(Base):
    __tablename__ = "endpoints"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    api_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_apis.id"), index=True
    )
    method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(String(1024))
    status: Mapped[str] = mapped_column(String(20), default="active")
    cost_rule: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
