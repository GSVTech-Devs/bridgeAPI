from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, model_validator

from app.domains.apis.models import APIAuthType, HTTPMethod

_SLUG_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
_METHODS = {m.value for m in HTTPMethod}


def _normalize_method(v: Optional[str]) -> Optional[str]:
    """None = não informado; '' = repassa o método do cliente (limpa); senão
    valida GET/POST/... e normaliza em maiúsculas."""
    if v is None:
        return None
    v = v.strip().upper()
    if v == "":
        return ""
    if v not in _METHODS:
        raise ValueError(f"request_method must be one of {sorted(_METHODS)} or empty")
    return v


def _normalize_openapi_url(v: Optional[str]) -> Optional[str]:
    """None = não informado; '' = limpa; senão exige http(s)."""
    if v is None:
        return None
    v = v.strip()
    if v == "":
        return ""
    if not v.startswith(("http://", "https://")):
        raise ValueError("openapi_url must start with http:// or https://")
    return v


class APICreateRequest(BaseModel):
    name: str
    slug: Optional[str] = None
    base_url: AnyHttpUrl
    url_template: Optional[str] = None
    request_method: Optional[str] = None
    request_body_template: Optional[str] = None
    master_key: Optional[str] = None
    auth_type: APIAuthType = APIAuthType.NONE
    cost_per_query: Optional[float] = None
    uses_proxy: bool = False
    uses_captcha: bool = False
    openapi_url: Optional[str] = None

    @field_validator("openapi_url")
    @classmethod
    def validate_openapi_url_create(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_openapi_url(v)

    @field_validator("request_method")
    @classmethod
    def validate_request_method(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_method(v)

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


class APIUpdateRequest(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    base_url: Optional[AnyHttpUrl] = None
    url_template: Optional[str] = None
    request_method: Optional[str] = None
    request_body_template: Optional[str] = None
    master_key: Optional[str] = None
    auth_type: Optional[APIAuthType] = None
    cost_per_query: Optional[float] = None
    uses_proxy: Optional[bool] = None
    uses_captcha: Optional[bool] = None
    openapi_url: Optional[str] = None

    @field_validator("openapi_url")
    @classmethod
    def validate_openapi_url_update(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_openapi_url(v)

    @field_validator("request_method")
    @classmethod
    def validate_request_method(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_method(v)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _SLUG_RE.match(v):
            raise ValueError(
                "slug must contain only letters, numbers, hyphens and underscores"
            )
        return v

    @model_validator(mode="after")
    def validate_url_template(self) -> "APIUpdateRequest":
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
    request_method: Optional[str] = None
    request_body_template: Optional[str] = None
    auth_type: str
    status: str
    cost_per_query: Optional[float] = None
    uses_proxy: bool = False
    uses_captcha: bool = False
    openapi_url: Optional[str] = None
    # Existe ≥1 operação de doc visível? Preenchido pelo catálogo do cliente.
    has_docs: bool = False
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
    request_method: Optional[str] = None
    request_body_template: Optional[str] = None
    auth_type: str
    status: str
    cost_per_query: Optional[float] = None
    uses_proxy: bool = False
    uses_captcha: bool = False
    openapi_url: Optional[str] = None
    created_at: datetime
    endpoints: list[EndpointResponse] = Field(default_factory=list)


class APIListResponse(BaseModel):
    items: list[APIResponse]
    total: int


# ------------------------------------------------ import de OpenAPI/Swagger
class OpenAPIImportRequest(BaseModel):
    url: str  # URL da doc da API (ex.: https://api.exemplo.com/openapi.json)


class ImportedOperation(BaseModel):
    method: str
    path: str
    summary: Optional[str] = None
    request_body_template: Optional[str] = None


class OpenAPIImportResponse(BaseModel):
    title: Optional[str] = None
    base_url: Optional[str] = None
    operations: list[ImportedOperation]


# -------------------------------------- import em massa (cria rascunhos inativos)
class BulkImportItem(BaseModel):
    name: str
    base_url: str
    request_method: Optional[str] = None
    request_body_template: Optional[str] = None
    auth_type: str = "none"
    cost_per_query: Optional[float] = None
    uses_proxy: bool = False
    uses_captcha: bool = False


class BulkImportRequest(BaseModel):
    items: list[BulkImportItem]


class BulkImportItemResult(BaseModel):
    name: str
    status: str  # "created" | "skipped"
    id: Optional[str] = None
    reason: Optional[str] = None


class BulkImportResponse(BaseModel):
    created: int
    skipped: int
    results: list[BulkImportItemResult]


# ------------------------------------------------ documentação do cliente (docs)
class DocParameter(BaseModel):
    name: str
    in_: Optional[str] = Field(default=None, alias="in")
    required: bool = False
    description: Optional[str] = None
    type: Optional[str] = None
    example: Optional[object] = None

    model_config = {"populate_by_name": True}


class DocResponseItem(BaseModel):
    status: str
    description: Optional[str] = None
    example: Optional[str] = None


class DocOperationResponse(BaseModel):
    """Operação da doc para o admin editar (inclui o flag `visible`)."""

    id: uuid.UUID
    method: str
    path: str
    summary: Optional[str] = None
    description: Optional[str] = None
    visible: bool = True
    parameters: list[DocParameter] = Field(default_factory=list)
    request_example: Optional[str] = None
    responses: list[DocResponseItem] = Field(default_factory=list)


class DocOperationListResponse(BaseModel):
    items: list[DocOperationResponse]
    total: int


class DocSyncResponse(BaseModel):
    created: int
    updated: int
    removed: int
    total: int


class DocOperationVisibilityRequest(BaseModel):
    visible: bool


# ------------------------------------------------ doc exibida ao cliente
class UserDocOperation(BaseModel):
    method: str
    path: str
    summary: Optional[str] = None
    description: Optional[str] = None
    parameters: list[DocParameter] = Field(default_factory=list)
    request_example: Optional[str] = None
    responses: list[DocResponseItem] = Field(default_factory=list)


class UserDocResponse(BaseModel):
    api_id: uuid.UUID
    api_name: str
    slug: Optional[str] = None
    base_url: str
    operations: list[UserDocOperation] = Field(default_factory=list)


def _parse_operation_json(raw: Optional[str]) -> dict:
    """Desserializa ``operation_json`` (defensivo: estrutura vazia se inválido)."""
    if not raw:
        return {"parameters": [], "request_example": None, "responses": []}
    try:
        import json

        data = json.loads(raw)
        if not isinstance(data, dict):
            return {"parameters": [], "request_example": None, "responses": []}
        return {
            "parameters": data.get("parameters") or [],
            "request_example": data.get("request_example"),
            "responses": data.get("responses") or [],
        }
    except Exception:  # noqa: BLE001
        return {"parameters": [], "request_example": None, "responses": []}


def build_doc_operation_response(row: object) -> DocOperationResponse:
    """Constrói a resposta de admin a partir de uma linha ApiDocOperation."""
    payload = _parse_operation_json(getattr(row, "operation_json", None))
    return DocOperationResponse(
        id=row.id,
        method=row.method,
        path=row.path,
        summary=row.summary,
        description=row.description,
        visible=row.visible,
        parameters=[DocParameter.model_validate(p) for p in payload["parameters"]],
        request_example=payload["request_example"],
        responses=[DocResponseItem.model_validate(r) for r in payload["responses"]],
    )


def build_user_doc_operation(row: object) -> UserDocOperation:
    """Constrói a operação exibida ao cliente a partir de uma linha ApiDocOperation."""
    payload = _parse_operation_json(getattr(row, "operation_json", None))
    return UserDocOperation(
        method=row.method,
        path=row.path,
        summary=row.summary,
        description=row.description,
        parameters=[DocParameter.model_validate(p) for p in payload["parameters"]],
        request_example=payload["request_example"],
        responses=[DocResponseItem.model_validate(r) for r in payload["responses"]],
    )
