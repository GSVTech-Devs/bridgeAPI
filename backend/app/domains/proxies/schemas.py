from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.domains.proxies.models import (
    ProxyOwnership,
    ProxyRotation,
    ProxyScheme,
    ProxyStatus,
    ProxyType,
)


# --------------------------------------------------------------------- pools
class ProxyPoolCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProxyPoolResponse(BaseModel):
    id: uuid.UUID
    account_id: Optional[uuid.UUID] = None
    name: str
    description: Optional[str] = None
    proxy_count: int = 0
    created_at: datetime


class ProxyPoolListResponse(BaseModel):
    items: list[ProxyPoolResponse]
    total: int


# ------------------------------------------------------------------- proxies
class ProxyCreate(BaseModel):
    name: str
    host: str
    port: int
    scheme: ProxyScheme = ProxyScheme.HTTP
    type: ProxyType = ProxyType.DATACENTER
    ownership: ProxyOwnership = ProxyOwnership.PLATFORM
    provider: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    rotation: ProxyRotation = ProxyRotation.STICKY
    session_ttl_s: Optional[int] = None
    priority: int = 100
    pool_id: Optional[uuid.UUID] = None


class ProxyUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    scheme: Optional[ProxyScheme] = None
    type: Optional[ProxyType] = None
    ownership: Optional[ProxyOwnership] = None
    provider: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    rotation: Optional[ProxyRotation] = None
    session_ttl_s: Optional[int] = None
    priority: Optional[int] = None
    pool_id: Optional[uuid.UUID] = None
    status: Optional[ProxyStatus] = None


class ProxyResponse(BaseModel):
    id: uuid.UUID
    account_id: Optional[uuid.UUID] = None
    pool_id: Optional[uuid.UUID] = None
    name: str
    provider: Optional[str] = None
    ownership: str
    type: str
    scheme: str
    host: str
    port: int
    username: Optional[str] = None
    has_password: bool = False
    rotation: str
    session_ttl_s: Optional[int] = None
    status: str
    priority: int
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None
    created_at: datetime


class ProxyListResponse(BaseModel):
    items: list[ProxyResponse]
    total: int


# ---------------------------------------------------- atribuição pool ↔ API
class APIPoolAssignRequest(BaseModel):
    proxy_pool_id: Optional[uuid.UUID] = None


# ------------------------- override do cliente: API → pool (resolução híbrida)
class ClientAssignmentItem(BaseModel):
    api_id: uuid.UUID
    api_name: str
    proxy_pool_id: Optional[uuid.UUID] = None  # override do cliente (se houver)


class ClientAssignmentListResponse(BaseModel):
    items: list[ClientAssignmentItem]


# --------------------------------------------------- config consumida pela SDK
class ProxyConfigItem(BaseModel):
    id: uuid.UUID
    name: str
    scheme: str
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    rotation: str
    session_ttl_s: Optional[int] = None
    priority: int


class ProxyConfigResponse(BaseModel):
    pool_id: Optional[uuid.UUID] = None
    pool_name: Optional[str] = None
    proxies: list[ProxyConfigItem]


# ------------------------------------------------ report de falha vindo da SDK
class ProxyReportRequest(BaseModel):
    proxy_id: uuid.UUID
    status: ProxyStatus = ProxyStatus.FAILING
    error_code: Optional[str] = None
    message: Optional[str] = None
