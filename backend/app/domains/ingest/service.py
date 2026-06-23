from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.domains.apis.models import ExternalAPI
from app.domains.apis.service import get_api_by_id
from app.domains.logs.service import APP_COLLECTION, mask_sensitive_values

SERVICE_TOKEN_PREFIX = "brgsvc"


async def generate_service_token(
    db: AsyncSession, api_id: str
) -> tuple[ExternalAPI, str]:
    """Gera (ou rotaciona) o service token de uma API. Retorna o token bruto
    apenas neste momento — só o hash fica persistido."""
    api = await get_api_by_id(db, api_id)

    prefix = secrets.token_hex(4)
    raw_token = f"{SERVICE_TOKEN_PREFIX}_{prefix}_{secrets.token_urlsafe(24)}"

    api.service_token_prefix = prefix
    api.service_token_hash = hash_password(raw_token)
    await db.commit()
    await db.refresh(api)
    return api, raw_token


async def authenticate_service_token(
    db: AsyncSession, presented_token: str
) -> ExternalAPI | None:
    """Resolve a API a partir de um service token, ou None se inválido."""
    if not presented_token.startswith(f"{SERVICE_TOKEN_PREFIX}_"):
        return None

    parts = presented_token.split("_", 2)
    if len(parts) != 3:
        return None

    prefix = parts[1]
    result = await db.execute(
        select(ExternalAPI).where(ExternalAPI.service_token_prefix == prefix)
    )
    api = result.scalar_one_or_none()
    if api is None or api.service_token_hash is None:
        return None
    if not verify_password(presented_token, api.service_token_hash):
        return None
    return api


async def write_app_logs(
    mongo_db: Any,
    api_id: str,
    entries: list[dict[str, Any]],
) -> int:
    """Persiste em lote os logs estruturados de uma API na coleção app_logs.

    Carimba api_id (do token, não do corpo), created_at e expires_at, e mascara
    valores sensíveis. Retorna a quantidade de documentos inseridos.
    """
    if not entries:
        return 0

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.app_log_retention_days)

    docs: list[dict[str, Any]] = []
    for entry in entries:
        doc = mask_sensitive_values(dict(entry))
        doc["api_id"] = api_id
        doc["created_at"] = now
        doc["expires_at"] = expires_at
        docs.append(doc)

    result = await mongo_db[APP_COLLECTION].insert_many(docs)
    return len(result.inserted_ids)
