from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, model_validator

from app.domains.apis.models import APIAuthType, HTTPMethod

_SLUG_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


class APICreateRequest(BaseModel):
    name: str
    slug: Optional[str] = None
    base_url: AnyHttpUrl
    url_template: Optional[str] = None
    master_key: Optional[str] = None
    auth_type: APIAuthType = APIAuthType.NONE
    cost_per_query: Optional[float] = None

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not _SLUG_RE.match(v):
                raise ValueError(
                    "slug must contain only letters, numbers, hyphens and underscores"
                )
        return v

    @model_validator(mode="after")
    def validate_url_template(self) -> "APICreateRequest":
        if self.url_template is not None:
            if "{query}" not in self.url_template:
                raise ValueError("url_template must contain the {query} placeholder")
            if not self.url_template.startswith(("http://", "https://")):
                raise ValueError(
                    "url_template must be a full URL starting with http:// or https://"
                )
        return self


class APIResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: Optional[str] = None
    base_url: str
    url_template: Optional[str] = None
    auth_type: str
    status: str
    cost_per_query: Optional[float] = None
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
    slug: Optional[str] = None
    base_url: str
    url_template: Optional[str] = None
    auth_type: str
    status: str
    cost_per_query: Optional[float] = None
    created_at: datetime
    endpoints: list[EndpointResponse] = Field(default_factory=list)


class APIListResponse(BaseModel):
    items: list[APIResponse]
    total: int
