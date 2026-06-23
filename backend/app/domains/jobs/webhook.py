"""Entrega de webhook do job (5b): POST assinado (HMAC-SHA256) no callback_url
do cliente quando o job termina, com algumas tentativas. Best-effort: o estado
da entrega vai para ``proxy_jobs.webhook_status`` e o resultado fica sempre
disponível por polling/SSE."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json

import httpx

from app.core.config import settings
from app.core.database import get_session_factory
from app.domains.jobs.service import set_webhook_status

SIGNATURE_HEADER = "x-bridge-signature"


def _secret() -> str:
    return settings.webhook_signing_secret or settings.app_secret_key


def sign(body: bytes) -> str:
    """Assinatura HMAC-SHA256 do corpo, formato ``sha256=<hex>``."""
    digest = hmac.new(_secret().encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


async def deliver(job_id: str, callback_url: str, payload: dict) -> bool:
    body = json.dumps(payload, default=str).encode()
    headers = {
        "content-type": "application/json",
        SIGNATURE_HEADER: sign(body),
        "x-correlation-id": str(payload.get("correlation_id", "")),
    }
    ok = False
    async with httpx.AsyncClient(timeout=settings.webhook_timeout_s) as client:
        for attempt in range(settings.webhook_max_attempts):
            try:
                resp = await client.post(callback_url, content=body, headers=headers)
                if resp.status_code < 400:
                    ok = True
                    break
            except Exception:
                pass
            await asyncio.sleep(0.5 * (attempt + 1))

    async with get_session_factory()() as session:
        try:
            await set_webhook_status(session, job_id, "delivered" if ok else "failed")
        except Exception:
            pass
    return ok
