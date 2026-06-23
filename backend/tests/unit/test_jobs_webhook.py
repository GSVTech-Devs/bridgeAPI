# Entrega de webhook do job (5b): assinatura HMAC + POST com retry.
from __future__ import annotations

import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domains.jobs import webhook


def test_sign_is_verifiable_hmac(monkeypatch) -> None:
    monkeypatch.setattr(webhook.settings, "webhook_signing_secret", "topsecret")
    body = b'{"job_id":"abc"}'
    sig = webhook.sign(body)
    assert sig.startswith("sha256=")
    expected = hmac.new(b"topsecret", body, hashlib.sha256).hexdigest()
    assert sig == f"sha256={expected}"


def test_sign_falls_back_to_app_secret(monkeypatch) -> None:
    monkeypatch.setattr(webhook.settings, "webhook_signing_secret", "")
    monkeypatch.setattr(webhook.settings, "app_secret_key", "fallback")
    body = b"x"
    expected = hmac.new(b"fallback", body, hashlib.sha256).hexdigest()
    assert webhook.sign(body) == f"sha256={expected}"


def _session_factory_mock():
    """Imita get_session_factory(): chamada → callable → context manager async."""
    session = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=cm)
    return MagicMock(return_value=factory), session


@pytest.mark.asyncio
async def test_deliver_success_marks_delivered(monkeypatch) -> None:
    monkeypatch.setattr(webhook.settings, "webhook_max_attempts", 3)
    resp = MagicMock(status_code=200)
    http_client = AsyncMock()
    http_client.post = AsyncMock(return_value=resp)
    http_cm = MagicMock()
    http_cm.__aenter__ = AsyncMock(return_value=http_client)
    http_cm.__aexit__ = AsyncMock(return_value=False)

    factory_mock, _ = _session_factory_mock()
    set_status = AsyncMock()

    with patch.object(webhook.httpx, "AsyncClient", return_value=http_cm), patch.object(
        webhook, "get_session_factory", factory_mock
    ), patch.object(webhook, "set_webhook_status", set_status):
        ok = await webhook.deliver(
            "job-1", "https://hook.example/cb", {"job_id": "job-1", "status": "done"}
        )

    assert ok is True
    http_client.post.assert_awaited_once()
    # assinatura presente no header
    _, kwargs = http_client.post.call_args
    assert webhook.SIGNATURE_HEADER in kwargs["headers"]
    set_status.assert_awaited_once()
    assert set_status.call_args.args[2] == "delivered"


@pytest.mark.asyncio
async def test_deliver_retries_then_fails(monkeypatch) -> None:
    monkeypatch.setattr(webhook.settings, "webhook_max_attempts", 3)
    monkeypatch.setattr(webhook.asyncio, "sleep", AsyncMock())  # sem espera real
    http_client = AsyncMock()
    http_client.post = AsyncMock(side_effect=Exception("boom"))
    http_cm = MagicMock()
    http_cm.__aenter__ = AsyncMock(return_value=http_client)
    http_cm.__aexit__ = AsyncMock(return_value=False)

    factory_mock, _ = _session_factory_mock()
    set_status = AsyncMock()

    with patch.object(webhook.httpx, "AsyncClient", return_value=http_cm), patch.object(
        webhook, "get_session_factory", factory_mock
    ), patch.object(webhook, "set_webhook_status", set_status):
        ok = await webhook.deliver("job-2", "https://hook.example/cb", {"job_id": "job-2"})

    assert ok is False
    assert http_client.post.await_count == 3  # tentou 3 vezes
    assert set_status.call_args.args[2] == "failed"
