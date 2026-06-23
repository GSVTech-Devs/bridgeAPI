from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from typing import Any

from app.core.config import settings

COLLECTION = "request_logs"
# Logs estruturados enviados pelas próprias APIs via POST /ingest/logs.
APP_COLLECTION = "app_logs"

SENSITIVE_HEADERS: frozenset[str] = frozenset(
    {
        "authorization",
        "x-api-key",
        "x-bridge-key",
        "cookie",
        "set-cookie",
        "proxy-authorization",
    }
)


def generate_correlation_id() -> str:
    return str(uuid.uuid4())


def mask_sensitive_headers(headers: dict[str, str]) -> dict[str, str]:
    """Mascara valores de headers sensíveis e valores com padrão de API key."""
    result: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADERS:
            result[key] = "[MASKED]"
        elif isinstance(value, str) and value.startswith("brg_"):
            result[key] = "[MASKED]"
        else:
            result[key] = value
    return result


def mask_sensitive_values(value: Any) -> Any:
    """Mascara recursivamente valores que parecem segredos (prefixo brg_).

    Aplicado ao corpo dos logs estruturados antes de persistir, complementando
    o mascaramento de headers feito em write_request_log.
    """
    if isinstance(value, str):
        return "[MASKED]" if value.startswith("brg_") else value
    if isinstance(value, dict):
        return {k: mask_sensitive_values(v) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_sensitive_values(v) for v in value]
    return value


async def write_request_log(
    mongo_db: Any,
    log_data: dict[str, Any],
) -> str:
    """Persiste um log de requisição no MongoDB com headers mascarados.

    Adiciona created_at e expires_at automaticamente.
    Retorna o inserted_id como string.
    """
    now = datetime.now(timezone.utc)
    doc = {
        **log_data,
        "request_headers": mask_sensitive_headers(log_data.get("request_headers", {})),
        "response_headers": mask_sensitive_headers(
            log_data.get("response_headers", {})
        ),
        "created_at": now,
        "expires_at": now + timedelta(hours=settings.log_retention_hours),
    }
    result = await mongo_db[COLLECTION].insert_one(doc)
    return str(result.inserted_id)


async def get_client_logs(
    mongo_db: Any,
    client_id: str,
    skip: int = 0,
    limit: int = 20,
    api_id: str | None = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    """Retorna logs paginados de um cliente específico."""
    query: dict[str, Any] = {"client_id": client_id}
    if api_id is not None:
        query["api_id"] = api_id
    if since is not None or until is not None:
        date_filter: dict[str, datetime] = {}
        if since is not None:
            date_filter["$gte"] = since
        if until is not None:
            date_filter["$lte"] = until
        query["created_at"] = date_filter
    cursor = mongo_db[COLLECTION].find(query).sort("created_at", -1)
    return await cursor.skip(skip).limit(limit).to_list(length=limit)


async def get_admin_logs(
    mongo_db: Any,
    skip: int = 0,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Retorna logs paginados de todos os clientes (acesso admin)."""
    cursor = mongo_db[COLLECTION].find({}).sort("created_at", -1)
    return await cursor.skip(skip).limit(limit).to_list(length=limit)


async def get_admin_error_logs(
    mongo_db: Any,
    api_id: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Retorna apenas logs de erro (status != 200), opcionalmente filtrados por api_id."""
    query: dict[str, Any] = {"status_code": {"$ne": 200}}
    if api_id is not None:
        query["api_id"] = api_id
    cursor = mongo_db[COLLECTION].find(query).sort("created_at", -1)
    return await cursor.skip(skip).limit(limit).to_list(length=limit)


async def get_app_logs(
    mongo_db: Any,
    correlation_id: str | None = None,
    api_id: str | None = None,
    level: str | None = None,
    event: str | None = None,
    error_code: str | None = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Retorna logs estruturados enviados pelas APIs (coleção app_logs)."""
    query: dict[str, Any] = {}
    if correlation_id is not None:
        query["correlation_id"] = correlation_id
    if api_id is not None:
        query["api_id"] = api_id
    if level is not None:
        query["level"] = level
    if event is not None:
        query["event"] = event
    if error_code is not None:
        query["error_code"] = error_code
    if since is not None or until is not None:
        date_filter: dict[str, datetime] = {}
        if since is not None:
            date_filter["$gte"] = since
        if until is not None:
            date_filter["$lte"] = until
        query["timestamp"] = date_filter
    cursor = mongo_db[APP_COLLECTION].find(query).sort("timestamp", -1)
    return await cursor.skip(skip).limit(limit).to_list(length=limit)


def _trace_sort_key(item: dict[str, Any]) -> Any:
    """Chave de ordenação da timeline: usa o instante mais relevante de cada fonte."""
    return item.get("timestamp") or item.get("created_at") or datetime.min.replace(
        tzinfo=timezone.utc
    )


async def get_trace_by_correlation_id(
    mongo_db: Any,
    correlation_id: str,
) -> list[dict[str, Any]]:
    """Timeline unificada de um correlation_id: junta logs do gateway
    (request_logs) e logs das APIs (app_logs), ordenados cronologicamente.

    É o painel de debug principal — um único ID liga toda a cadeia.
    """
    gw_cursor = mongo_db[COLLECTION].find({"correlation_id": correlation_id})
    gateway_logs = await gw_cursor.to_list(length=1000)
    app_logs = await get_app_logs(
        mongo_db, correlation_id=correlation_id, limit=1000
    )

    timeline: list[dict[str, Any]] = []
    for doc in gateway_logs:
        timeline.append({**doc, "source": "gateway"})
    for doc in app_logs:
        timeline.append({**doc, "source": "app"})

    timeline.sort(key=_trace_sort_key)
    return timeline
