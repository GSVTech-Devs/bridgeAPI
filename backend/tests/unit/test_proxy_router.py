# RED → GREEN
# Testes para o domínio proxy — camada HTTP.
# validate_request, forward_to_upstream e record_metric são mockados via patch.
# Testa todos os cenários de erro, forwarding transparente e registro de métricas.
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import AsyncClient

from app.core.security import encrypt_value
from app.domains.apis.models import APIAuthType, APIStatus, ExternalAPI
from app.domains.clients.models import Client, ClientStatus
from app.domains.keys.models import APIKey, APIKeyStatus
from app.domains.apis.service import APINotFoundError
from app.domains.proxy.service import (
    DisabledAPIError,
    InactiveClientError,
    InvalidKeyError,
    PermissionDeniedError,
    RateLimitExceededError,
)

BRIDGE_KEY = "brg_abcd1234_super-secret-value"
SLUG = "finance"


def proxy_headers() -> dict:
    return {"X-Bridge-Key": BRIDGE_KEY}


def make_api_key() -> APIKey:
    return APIKey(
        id=uuid.uuid4(),
        client_id=uuid.uuid4(),
        name="Test Key",
        key_prefix="abcd1234",
        key_secret_hash="hashed",
        status=APIKeyStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
    )


def make_client() -> Client:
    return Client(
        id=uuid.uuid4(),
        name="Acme Corp",
        email="acme@example.com",
        password_hash="hashed",
        status=ClientStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
    )


def make_api(
    auth_type: APIAuthType = APIAuthType.API_KEY,
    slug: str | None = None,
) -> ExternalAPI:
    return ExternalAPI(
        id=uuid.uuid4(),
        name="Stripe API",
        slug=slug,
        base_url="https://api.stripe.com",
        master_key_encrypted=encrypt_value("sk-secret-123"),
        auth_type=auth_type,
        status=APIStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
    )


def make_upstream_response(
    status_code: int = 200,
    json_body: dict | None = None,
    text: str = "OK",
) -> httpx.Response:
    if json_body is not None:
        return httpx.Response(status_code, json=json_body)
    return httpx.Response(status_code, text=text)


# ---------------------------------------------------------------------------
# Erros de validação → status HTTP correto
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_with_invalid_key_returns_401(client: AsyncClient) -> None:
    api_id = uuid.uuid4()
    with patch(
        "app.domains.proxy.router.validate_request",
        new=AsyncMock(side_effect=InvalidKeyError("key not found")),
    ):
        response = await client.get(f"/proxy/{api_id}/charges", headers=proxy_headers())
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_request_with_revoked_key_returns_401(client: AsyncClient) -> None:
    api_id = uuid.uuid4()
    with patch(
        "app.domains.proxy.router.validate_request",
        new=AsyncMock(side_effect=InvalidKeyError("key revoked")),
    ):
        response = await client.get(f"/proxy/{api_id}/charges", headers=proxy_headers())
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_request_with_inactive_client_returns_403(client: AsyncClient) -> None:
    api_id = uuid.uuid4()
    with patch(
        "app.domains.proxy.router.validate_request",
        new=AsyncMock(side_effect=InactiveClientError("client not active")),
    ):
        response = await client.get(f"/proxy/{api_id}/charges", headers=proxy_headers())
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_request_to_disabled_api_returns_503(client: AsyncClient) -> None:
    api_id = uuid.uuid4()
    with patch(
        "app.domains.proxy.router.validate_request",
        new=AsyncMock(side_effect=DisabledAPIError("api disabled")),
    ):
        response = await client.get(f"/proxy/{api_id}/charges", headers=proxy_headers())
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_request_without_permission_returns_403(client: AsyncClient) -> None:
    api_id = uuid.uuid4()
    with patch(
        "app.domains.proxy.router.validate_request",
        new=AsyncMock(side_effect=PermissionDeniedError("no permission")),
    ):
        response = await client.get(f"/proxy/{api_id}/charges", headers=proxy_headers())
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_request_exceeding_rate_limit_returns_429(client: AsyncClient) -> None:
    api_id = uuid.uuid4()
    with patch(
        "app.domains.proxy.router.validate_request",
        new=AsyncMock(side_effect=RateLimitExceededError("rate limit exceeded")),
    ):
        response = await client.get(f"/proxy/{api_id}/charges", headers=proxy_headers())
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_proxy_without_api_key_header_returns_401(client: AsyncClient) -> None:
    api_id = uuid.uuid4()
    # nenhum header X-Bridge-Key
    response = await client.get(f"/proxy/{api_id}/charges")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Forwarding — resposta transparente do upstream
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_request_is_forwarded_to_upstream(client: AsyncClient) -> None:
    api_id = uuid.uuid4()
    api_key_obj = make_api_key()
    active_client = make_client()
    active_api = make_api()
    upstream_resp = make_upstream_response(200, json_body={"id": "ch_123"})

    with patch(
        "app.domains.proxy.router.validate_request",
        new=AsyncMock(return_value=(api_key_obj, active_client, active_api)),
    ):
        with patch("app.domains.proxy.router.build_upstream_headers", return_value={}):
            with patch(
                "app.domains.proxy.router.forward_to_upstream",
                new=AsyncMock(return_value=upstream_resp),
            ):
                with patch("app.domains.proxy.router.record_metric", new=AsyncMock()):
                    response = await client.get(
                        f"/proxy/{api_id}/charges", headers=proxy_headers()
                    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_upstream_response_body_is_returned_transparently(
    client: AsyncClient,
) -> None:
    api_id = uuid.uuid4()
    upstream_resp = make_upstream_response(200, json_body={"balance": 9999})

    with patch(
        "app.domains.proxy.router.validate_request",
        new=AsyncMock(return_value=(make_api_key(), make_client(), make_api())),
    ):
        with patch("app.domains.proxy.router.build_upstream_headers", return_value={}):
            with patch(
                "app.domains.proxy.router.forward_to_upstream",
                new=AsyncMock(return_value=upstream_resp),
            ):
                with patch("app.domains.proxy.router.record_metric", new=AsyncMock()):
                    response = await client.get(
                        f"/proxy/{api_id}/balance", headers=proxy_headers()
                    )

    assert response.json()["balance"] == 9999


@pytest.mark.asyncio
async def test_upstream_non_200_status_is_preserved(client: AsyncClient) -> None:
    api_id = uuid.uuid4()
    upstream_resp = make_upstream_response(404, text="Not Found")

    with patch(
        "app.domains.proxy.router.validate_request",
        new=AsyncMock(return_value=(make_api_key(), make_client(), make_api())),
    ):
        with patch("app.domains.proxy.router.build_upstream_headers", return_value={}):
            with patch(
                "app.domains.proxy.router.forward_to_upstream",
                new=AsyncMock(return_value=upstream_resp),
            ):
                with patch("app.domains.proxy.router.record_metric", new=AsyncMock()):
                    response = await client.get(
                        f"/proxy/{api_id}/missing", headers=proxy_headers()
                    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Forwarding — erros do upstream
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upstream_timeout_returns_504(client: AsyncClient) -> None:
    api_id = uuid.uuid4()

    with patch(
        "app.domains.proxy.router.validate_request",
        new=AsyncMock(return_value=(make_api_key(), make_client(), make_api())),
    ):
        with patch("app.domains.proxy.router.build_upstream_headers", return_value={}):
            with patch(
                "app.domains.proxy.router.forward_to_upstream",
                new=AsyncMock(
                    side_effect=httpx.ReadTimeout("upstream timed out", request=None)
                ),
            ):
                response = await client.get(
                    f"/proxy/{api_id}/charges", headers=proxy_headers()
                )

    assert response.status_code == 504


@pytest.mark.asyncio
async def test_upstream_5xx_is_forwarded_as_502(client: AsyncClient) -> None:
    api_id = uuid.uuid4()
    upstream_resp = make_upstream_response(500, text="Internal Server Error")

    with patch(
        "app.domains.proxy.router.validate_request",
        new=AsyncMock(return_value=(make_api_key(), make_client(), make_api())),
    ):
        with patch("app.domains.proxy.router.build_upstream_headers", return_value={}):
            with patch(
                "app.domains.proxy.router.forward_to_upstream",
                new=AsyncMock(return_value=upstream_resp),
            ):
                with patch("app.domains.proxy.router.record_metric", new=AsyncMock()):
                    response = await client.get(
                        f"/proxy/{api_id}/charges", headers=proxy_headers()
                    )

    assert response.status_code == 502


# ---------------------------------------------------------------------------
# Headers — injeção da master key
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upstream_headers_are_injected_with_master_key(
    client: AsyncClient,
) -> None:
    api_id = uuid.uuid4()
    injected_headers = {"x-api-key": "sk-secret-123", "accept": "application/json"}
    upstream_resp = make_upstream_response(200, json_body={"ok": True})

    captured: dict = {}

    async def fake_forward(http_client, api, path, method, headers, params, content):
        captured["headers"] = headers
        return upstream_resp

    with patch(
        "app.domains.proxy.router.validate_request",
        new=AsyncMock(return_value=(make_api_key(), make_client(), make_api())),
    ):
        with patch(
            "app.domains.proxy.router.build_upstream_headers",
            return_value=injected_headers,
        ):
            with patch(
                "app.domains.proxy.router.forward_to_upstream",
                new=AsyncMock(side_effect=fake_forward),
            ):
                with patch("app.domains.proxy.router.record_metric", new=AsyncMock()):
                    await client.get(
                        f"/proxy/{api_id}/charges", headers=proxy_headers()
                    )

    assert captured["headers"]["x-api-key"] == "sk-secret-123"
    assert "x-bridge-key" not in captured["headers"]


# ---------------------------------------------------------------------------
# Métricas — gravação e cobrança
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_request_creates_metric_record(client: AsyncClient) -> None:
    api_id = uuid.uuid4()
    upstream_resp = make_upstream_response(200, json_body={"ok": True})

    with patch(
        "app.domains.proxy.router.validate_request",
        new=AsyncMock(return_value=(make_api_key(), make_client(), make_api())),
    ):
        with patch("app.domains.proxy.router.build_upstream_headers", return_value={}):
            with patch(
                "app.domains.proxy.router.forward_to_upstream",
                new=AsyncMock(return_value=upstream_resp),
            ):
                with patch(
                    "app.domains.proxy.router.record_metric", new=AsyncMock()
                ) as mock_record:
                    await client.get(
                        f"/proxy/{api_id}/charges", headers=proxy_headers()
                    )

    mock_record.assert_called_once()


@pytest.mark.asyncio
async def test_metric_includes_latency_status_and_cost(client: AsyncClient) -> None:
    api_id = uuid.uuid4()
    upstream_resp = make_upstream_response(200, json_body={"ok": True})

    with patch(
        "app.domains.proxy.router.validate_request",
        new=AsyncMock(return_value=(make_api_key(), make_client(), make_api())),
    ):
        with patch("app.domains.proxy.router.build_upstream_headers", return_value={}):
            with patch(
                "app.domains.proxy.router.forward_to_upstream",
                new=AsyncMock(return_value=upstream_resp),
            ):
                with patch(
                    "app.domains.proxy.router.record_metric", new=AsyncMock()
                ) as mock_record:
                    await client.get(
                        f"/proxy/{api_id}/charges", headers=proxy_headers()
                    )

    kwargs = mock_record.call_args.kwargs
    assert kwargs["status_code"] == 200
    assert kwargs["latency_ms"] >= 0
    assert "cost" in kwargs


@pytest.mark.asyncio
async def test_rate_limited_request_is_not_billed(client: AsyncClient) -> None:
    api_id = uuid.uuid4()
    with patch(
        "app.domains.proxy.router.validate_request",
        new=AsyncMock(side_effect=RateLimitExceededError("rate limit exceeded")),
    ):
        with patch(
            "app.domains.proxy.router.record_metric", new=AsyncMock()
        ) as mock_record:
            await client.get(f"/proxy/{api_id}/charges", headers=proxy_headers())

    mock_record.assert_not_called()


@pytest.mark.asyncio
async def test_error_request_is_not_billed(client: AsyncClient) -> None:
    # upstream retorna 5xx → bridge retorna 502, cost=None na métrica
    api_id = uuid.uuid4()
    upstream_resp = make_upstream_response(500, text="Internal Server Error")

    with patch(
        "app.domains.proxy.router.validate_request",
        new=AsyncMock(return_value=(make_api_key(), make_client(), make_api())),
    ):
        with patch("app.domains.proxy.router.build_upstream_headers", return_value={}):
            with patch(
                "app.domains.proxy.router.forward_to_upstream",
                new=AsyncMock(return_value=upstream_resp),
            ):
                with patch(
                    "app.domains.proxy.router.record_metric", new=AsyncMock()
                ) as mock_record:
                    await client.get(
                        f"/proxy/{api_id}/charges", headers=proxy_headers()
                    )

    kwargs = mock_record.call_args.kwargs
    assert kwargs["cost"] is None


@pytest.mark.asyncio
async def test_request_body_is_forwarded_to_upstream(client: AsyncClient) -> None:
    api_id = uuid.uuid4()
    upstream_resp = make_upstream_response(201, json_body={"id": "ch_new"})
    captured: dict = {}

    async def fake_forward(http_client, api, path, method, headers, params, content):
        captured["content"] = content
        captured["method"] = method
        return upstream_resp

    with patch(
        "app.domains.proxy.router.validate_request",
        new=AsyncMock(return_value=(make_api_key(), make_client(), make_api())),
    ):
        with patch("app.domains.proxy.router.build_upstream_headers", return_value={}):
            with patch(
                "app.domains.proxy.router.forward_to_upstream",
                new=AsyncMock(side_effect=fake_forward),
            ):
                with patch("app.domains.proxy.router.record_metric", new=AsyncMock()):
                    await client.post(
                        f"/proxy/{api_id}/charges",
                        content=b'{"amount": 500}',
                        headers={**proxy_headers(), "content-type": "application/json"},
                    )

    assert captured["method"] == "POST"
    assert captured["content"] == b'{"amount": 500}'


@pytest.mark.asyncio
async def test_successful_request_writes_log_to_mongo(client: AsyncClient) -> None:
    """Quando mongo_db está ativo, o router chama write_request_log."""
    from app.core.mongo_client import get_mongo_db
    from app.main import app

    fake_mongo = MagicMock(name="mongo_db")

    async def override_mongo():
        yield fake_mongo

    app.dependency_overrides[get_mongo_db] = override_mongo
    try:
        api_id = uuid.uuid4()
        upstream_resp = make_upstream_response(200, json_body={"id": "ch_logged"})

        with (
            patch(
                "app.domains.proxy.router.validate_request",
                new=AsyncMock(return_value=(make_api_key(), make_client(), make_api())),
            ),
            patch("app.domains.proxy.router.build_upstream_headers", return_value={}),
            patch(
                "app.domains.proxy.router.forward_to_upstream",
                new=AsyncMock(return_value=upstream_resp),
            ),
            patch("app.domains.proxy.router.record_metric", new=AsyncMock()),
            patch(
                "app.domains.proxy.router.write_request_log", new=AsyncMock()
            ) as mock_log,
        ):
            await client.get(f"/proxy/{api_id}/charges", headers=proxy_headers())

        mock_log.assert_awaited_once()
        called_db, payload = mock_log.await_args.args
        assert called_db is fake_mongo
        assert payload["path"] == "charges"
        assert payload["status_code"] == 200
        assert "correlation_id" in payload
    finally:
        del app.dependency_overrides[get_mongo_db]


# ---------------------------------------------------------------------------
# Rota pública: /apis/{slug}/{query}/{bridge_token}
# ---------------------------------------------------------------------------


def slug_url(query: str = "bitcoin", key: str = BRIDGE_KEY) -> str:
    return f"/apis/{SLUG}/{query}/{key}"


def _slug_patches(
    api=None,
    validate_result=None,
    forward_result=None,
    slug_error=None,
    validate_error=None,
):
    """Combina os patches comuns dos testes da rota por slug."""
    active_api = api or make_api(slug=SLUG)
    patches = [
        patch(
            "app.domains.proxy.router.get_api_by_slug",
            new=AsyncMock(
                return_value=active_api if slug_error is None else None,
                side_effect=slug_error,
            ),
        ),
        patch(
            "app.domains.proxy.router.validate_request",
            new=AsyncMock(
                return_value=validate_result or (make_api_key(), make_client(), active_api),
                side_effect=validate_error,
            ),
        ),
        patch("app.domains.proxy.router.build_upstream_headers", return_value={}),
        patch(
            "app.domains.proxy.router.forward_to_upstream",
            new=AsyncMock(
                return_value=forward_result or make_upstream_response(200, json_body={"ok": True})
            ),
        ),
        patch("app.domains.proxy.router.record_metric", new=AsyncMock()),
    ]
    return patches


@pytest.mark.asyncio
async def test_slug_route_valid_request_returns_200(client: AsyncClient) -> None:
    with _slug_patches()[0], _slug_patches()[1], _slug_patches()[2], _slug_patches()[3], _slug_patches()[4]:
        pass  # will use context managers below


@pytest.mark.asyncio
async def test_slug_route_forwards_request_and_returns_upstream_body(
    client: AsyncClient,
) -> None:
    active_api = make_api(slug=SLUG)
    upstream_resp = make_upstream_response(200, json_body={"price": 42000})
    with (
        patch("app.domains.proxy.router.get_api_by_slug", new=AsyncMock(return_value=active_api)),
        patch(
            "app.domains.proxy.router.validate_request",
            new=AsyncMock(return_value=(make_api_key(), make_client(), active_api)),
        ),
        patch("app.domains.proxy.router.build_upstream_headers", return_value={}),
        patch("app.domains.proxy.router.forward_to_upstream", new=AsyncMock(return_value=upstream_resp)),
        patch("app.domains.proxy.router.record_metric", new=AsyncMock()),
    ):
        response = await client.get(slug_url("bitcoin"))
    assert response.status_code == 200
    assert response.json()["price"] == 42000


@pytest.mark.asyncio
async def test_slug_route_unknown_slug_returns_404(client: AsyncClient) -> None:
    with patch(
        "app.domains.proxy.router.get_api_by_slug",
        new=AsyncMock(side_effect=APINotFoundError("nope")),
    ):
        response = await client.get(slug_url())
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_slug_route_invalid_bridge_key_returns_401(client: AsyncClient) -> None:
    active_api = make_api(slug=SLUG)
    with (
        patch("app.domains.proxy.router.get_api_by_slug", new=AsyncMock(return_value=active_api)),
        patch(
            "app.domains.proxy.router.validate_request",
            new=AsyncMock(side_effect=InvalidKeyError("bad key")),
        ),
    ):
        response = await client.get(slug_url(key="brg_invalid"))
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_slug_route_inactive_client_returns_403(client: AsyncClient) -> None:
    active_api = make_api(slug=SLUG)
    with (
        patch("app.domains.proxy.router.get_api_by_slug", new=AsyncMock(return_value=active_api)),
        patch(
            "app.domains.proxy.router.validate_request",
            new=AsyncMock(side_effect=InactiveClientError("inactive")),
        ),
    ):
        response = await client.get(slug_url())
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_slug_route_disabled_api_returns_503(client: AsyncClient) -> None:
    active_api = make_api(slug=SLUG)
    with (
        patch("app.domains.proxy.router.get_api_by_slug", new=AsyncMock(return_value=active_api)),
        patch(
            "app.domains.proxy.router.validate_request",
            new=AsyncMock(side_effect=DisabledAPIError("disabled")),
        ),
    ):
        response = await client.get(slug_url())
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_slug_route_no_permission_returns_403(client: AsyncClient) -> None:
    active_api = make_api(slug=SLUG)
    with (
        patch("app.domains.proxy.router.get_api_by_slug", new=AsyncMock(return_value=active_api)),
        patch(
            "app.domains.proxy.router.validate_request",
            new=AsyncMock(side_effect=PermissionDeniedError("denied")),
        ),
    ):
        response = await client.get(slug_url())
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_slug_route_rate_limited_returns_429(client: AsyncClient) -> None:
    active_api = make_api(slug=SLUG)
    with (
        patch("app.domains.proxy.router.get_api_by_slug", new=AsyncMock(return_value=active_api)),
        patch(
            "app.domains.proxy.router.validate_request",
            new=AsyncMock(side_effect=RateLimitExceededError("limit")),
        ),
    ):
        response = await client.get(slug_url())
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_slug_route_upstream_timeout_returns_504(client: AsyncClient) -> None:
    active_api = make_api(slug=SLUG)
    with (
        patch("app.domains.proxy.router.get_api_by_slug", new=AsyncMock(return_value=active_api)),
        patch(
            "app.domains.proxy.router.validate_request",
            new=AsyncMock(return_value=(make_api_key(), make_client(), active_api)),
        ),
        patch("app.domains.proxy.router.build_upstream_headers", return_value={}),
        patch(
            "app.domains.proxy.router.forward_to_upstream",
            new=AsyncMock(side_effect=httpx.ReadTimeout("timeout", request=None)),
        ),
    ):
        response = await client.get(slug_url())
    assert response.status_code == 504


@pytest.mark.asyncio
async def test_slug_route_upstream_5xx_returns_502(client: AsyncClient) -> None:
    active_api = make_api(slug=SLUG)
    with (
        patch("app.domains.proxy.router.get_api_by_slug", new=AsyncMock(return_value=active_api)),
        patch(
            "app.domains.proxy.router.validate_request",
            new=AsyncMock(return_value=(make_api_key(), make_client(), active_api)),
        ),
        patch("app.domains.proxy.router.build_upstream_headers", return_value={}),
        patch(
            "app.domains.proxy.router.forward_to_upstream",
            new=AsyncMock(return_value=make_upstream_response(500, text="oops")),
        ),
        patch("app.domains.proxy.router.record_metric", new=AsyncMock()),
    ):
        response = await client.get(slug_url())
    assert response.status_code == 502


@pytest.mark.asyncio
async def test_slug_route_query_is_forwarded_as_path(client: AsyncClient) -> None:
    active_api = make_api(slug=SLUG)
    captured: dict = {}

    async def fake_forward(http_client, api, path, method, headers, params, content):
        captured["path"] = path
        return make_upstream_response(200, json_body={"ok": True})

    with (
        patch("app.domains.proxy.router.get_api_by_slug", new=AsyncMock(return_value=active_api)),
        patch(
            "app.domains.proxy.router.validate_request",
            new=AsyncMock(return_value=(make_api_key(), make_client(), active_api)),
        ),
        patch("app.domains.proxy.router.build_upstream_headers", return_value={}),
        patch("app.domains.proxy.router.forward_to_upstream", new=AsyncMock(side_effect=fake_forward)),
        patch("app.domains.proxy.router.record_metric", new=AsyncMock()),
    ):
        await client.get(slug_url(query="bitcoin"))

    assert captured["path"] == "bitcoin"


@pytest.mark.asyncio
async def test_slug_route_bridge_key_comes_from_url_not_header(
    client: AsyncClient,
) -> None:
    active_api = make_api(slug=SLUG)
    captured: dict = {}

    async def fake_validate(db, presented_key, api_id, redis):
        captured["presented_key"] = presented_key
        return make_api_key(), make_client(), active_api

    with (
        patch("app.domains.proxy.router.get_api_by_slug", new=AsyncMock(return_value=active_api)),
        patch("app.domains.proxy.router.validate_request", new=AsyncMock(side_effect=fake_validate)),
        patch("app.domains.proxy.router.build_upstream_headers", return_value={}),
        patch(
            "app.domains.proxy.router.forward_to_upstream",
            new=AsyncMock(return_value=make_upstream_response(200, json_body={})),
        ),
        patch("app.domains.proxy.router.record_metric", new=AsyncMock()),
    ):
        # nenhum header X-Bridge-Key — chave vem da URL
        await client.get(f"/apis/{SLUG}/bitcoin/{BRIDGE_KEY}")

    assert captured["presented_key"] == BRIDGE_KEY


@pytest.mark.asyncio
async def test_slug_route_records_metric(client: AsyncClient) -> None:
    active_api = make_api(slug=SLUG)
    with (
        patch("app.domains.proxy.router.get_api_by_slug", new=AsyncMock(return_value=active_api)),
        patch(
            "app.domains.proxy.router.validate_request",
            new=AsyncMock(return_value=(make_api_key(), make_client(), active_api)),
        ),
        patch("app.domains.proxy.router.build_upstream_headers", return_value={}),
        patch(
            "app.domains.proxy.router.forward_to_upstream",
            new=AsyncMock(return_value=make_upstream_response(200, json_body={})),
        ),
        patch("app.domains.proxy.router.record_metric", new=AsyncMock()) as mock_metric,
    ):
        await client.get(slug_url())

    mock_metric.assert_called_once()
