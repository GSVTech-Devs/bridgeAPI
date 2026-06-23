from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.domains.captcha.models import CaptchaStatus


# ----------------------------------------------------------------- providers
class CaptchaCreate(BaseModel):
    name: str
    provider: Optional[str] = None
    api_key: Optional[str] = None
    balance_usd: Optional[float] = None
    priority: int = 100


class CaptchaUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None
    balance_usd: Optional[float] = None
    priority: Optional[int] = None
    status: Optional[CaptchaStatus] = None


class CaptchaResponse(BaseModel):
    id: uuid.UUID
    api_id: uuid.UUID
    account_id: Optional[uuid.UUID] = None
    name: str
    provider: Optional[str] = None
    has_api_key: bool = False
    balance_usd: Optional[float] = None
    priority: int
    status: str
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None
    created_at: datetime


class CaptchaListResponse(BaseModel):
    items: list[CaptchaResponse]
    total: int


# --------------------------------------------------- config consumida pela SDK
class CaptchaConfigItem(BaseModel):
    id: uuid.UUID
    name: str
    provider: Optional[str] = None
    api_key: Optional[str] = None
    balance_usd: Optional[float] = None
    priority: int


class CaptchaConfigResponse(BaseModel):
    providers: list[CaptchaConfigItem]


# ------------------------------------------------ report de falha vindo da SDK
class CaptchaReportRequest(BaseModel):
    provider_id: uuid.UUID
    status: CaptchaStatus = CaptchaStatus.FAILING
    error_code: Optional[str] = None
    message: Optional[str] = None
    balance_usd: Optional[float] = None  # saldo restante reportado pela SDK


# --------------------------------------------- item do monitoramento agregado
class CaptchaMonitorItem(BaseModel):
    id: uuid.UUID
    api_id: uuid.UUID
    api_name: str
    account_id: Optional[uuid.UUID] = None
    name: str
    provider: Optional[str] = None
    balance_usd: Optional[float] = None
    status: str
    priority: int
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None


class CaptchaMonitorResponse(BaseModel):
    items: list[CaptchaMonitorItem]
    total: int
