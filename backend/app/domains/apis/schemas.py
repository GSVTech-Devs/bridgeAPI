from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator

from app.domains.apis.models import APIAuthType, HTTPMethod


class APICreateRequest(BaseModel):
    name: str
    base_url: AnyHttpUrl
    master_key: Optional[str] = None
    auth_type: APIAuthType = APIAuthType.NONE


class APIResponse(BaseModel):
    id: uuid.UUID
    name: str
    base_url: str
    auth_type: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class EndpointCreateRequest(BaseModel):
    method: HTTPMethod
    path: str
    cost_rule: Optional[float] = None

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("Endpoint path must start with '/'")
        return value


class EndpointResponse(BaseModel):
    id: uuid.UUID
    api_id: uuid.UUID
    method: str
    path: str
    status: str
    cost_rule: Optional[float]
    created_at: datetime

    model_config = {"from_attributes": True}


class APIDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    base_url: str
    auth_type: str
    status: str
    created_at: datetime
    endpoints: List[EndpointResponse] = Field(default_factory=list)


class APIListResponse(BaseModel):
    items: List[APIResponse]
    total: int
