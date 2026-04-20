from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings

COLLECTION = "request_logs"

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
) -> list[dict[str, Any]]:
    """Retorna logs paginados de um cliente específico."""
    cursor = mongo_db[COLLECTION].find({"client_id": client_id})
    return await cursor.skip(skip).limit(limit).to_list(length=limit)


async def get_admin_logs(
    mongo_db: Any,
    skip: int = 0,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Retorna logs paginados de todos os clientes (acesso admin)."""
    cursor = mongo_db[COLLECTION].find({}).sort("created_at", -1)
    return await cursor.skip(skip).limit(limit).to_list(length=limit)
