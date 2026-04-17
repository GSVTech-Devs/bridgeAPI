# RED → GREEN
# Testes unitários para app/domains/proxy/service.py.
# Cobre toda a pipeline de validação, injeção de headers e forwarding.
# forward_to_upstream usa httpx.MockTransport para simular o upstream real.
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.security import encrypt_value
from app.domains.apis.models import APIAuthType, APIStatus, ExternalAPI
from app.domains.clients.models import Client, ClientStatus
from app.domains.keys.models import APIKey, APIKeyStatus
from app.domains.permissions.models import Permission
from app.domains.proxy.service import (
    DisabledAPIError,
    InactiveClientError,
    InvalidKeyError,
    PermissionDeniedError,
    RateLimitExceededError,
    _build_url_from_template,
    build_upstream_headers,
    forward_to_upstream,
    validate_request,
)

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def make_api_key(
    status: APIKeyStatus = APIKeyStatus.ACTIVE,
    client_id: uuid.UUID | None = None,
    api_id: uuid.UUID | None = None,
) -> APIKey:
    return APIKey(
        id=uuid.uuid4(),
        client_id=client_id or uuid.uuid4(),
        api_id=api_id,
        name="Test Key",
        key_prefix="abcd1234",
        key_secret_hash="hashed",
        status=status,
        created_at=datetime.now(timezone.utc),
    )


def make_client(status: ClientStatus = ClientStatus.ACTIVE) -> Client:
    return Client(
        id=uuid.uuid4(),
        name="Acme Corp",
        email="acme@example.com",
        password_hash="hashed",
        status=status,
        created_at=datetime.now(timezone.utc),
    )


def make_api(
    status: APIStatus = APIStatus.ACTIVE,
    auth_type: APIAuthType = APIAuthType.API_KEY,
    master_key: str = "sk-secret-123",
    url_template: str | None = None,
) -> ExternalAPI:
    encrypted = encrypt_value(master_key) if master_key else None
    return ExternalAPI(
        id=uuid.uuid4(),
        name="Stripe API",
        base_url="https://api.stripe.com",
        url_template=url_template,
        master_key_encrypted=encrypted,
        auth_type=auth_type,
        status=status,
        created_at=datetime.now(timezone.utc),
    )


def make_permission(
    client_id: uuid.UUID | None = None,
    api_id: uuid.UUID | None = None,
) -> Permission:
    return Permission(
        id=uuid.uuid4(),
        client_id=client_id or uuid.uuid4(),
        api_id=api_id or uuid.uuid4(),
        granted_at=datetime.now(timezone.utc),
        revoked_at=None,
    )


def make_execute_result(
    scalar_result=None,
    scalars_result=None,
) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_result
    result.scalars.return_value.all.return_value = scalars_result or []
    return result


def make_db(*results: MagicMock) -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.side_effect = list(results)
    return db


# ---------------------------------------------------------------------------
# validate_request — api_id bound to key
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_key_bound_to_different_api_raises_permission_denied() -> None:
    bound_api_id = uuid.uuid4()
    requested_api_id = uuid.uuid4()  # different
    api_key = make_api_key(api_id=bound_api_id)
    active_client = make_client()
    db = make_db(make_execute_result(scalar_result=active_client))

    with patch(
        "app.domains.proxy.service.authenticate_api_key",
        new=AsyncMock(return_value=api_key),
    ):
        with pytest.raises(PermissionDeniedError):
            await validate_request(db, "brg_xxx_yyy", str(requested_api_id))


@pytest.mark.asyncio
async def test_key_bound_to_correct_api_passes_api_id_check() -> None:
    api_id = uuid.uuid4()
    api_key = make_api_key(api_id=api_id)
    active_client = make_client()
    active_api = make_api()
    active_api.id = api_id
    permission = make_permission(client_id=active_client.id, api_id=api_id)
    db = make_db(
        make_execute_result(scalar_result=active_client),
        make_execute_result(scalar_result=permission),
    )

    with patch(
        "app.domains.proxy.service.authenticate_api_key",
        new=AsyncMock(return_value=api_key),
    ):
        with patch(
            "app.domains.proxy.service.get_api_by_id",
            new=AsyncMock(return_value=active_api),
        ):
            result_key, _, _ = await validate_request(db, "brg_xxx_yyy", str(api_id))

    assert result_key is api_key


# ---------------------------------------------------------------------------
# validate_request — validação da API key
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_api_key_raises_error() -> None:
    db = AsyncMock()
    with patch(
        "app.domains.proxy.service.authenticate_api_key",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(InvalidKeyError):
            await validate_request(db, "brg_invalid_key", str(uuid.uuid4()))


@pytest.mark.asyncio
async def test_revoked_api_key_raises_error() -> None:
    # authenticate_api_key já retorna None para chaves revogadas
    db = AsyncMock()
    with patch(
        "app.domains.proxy.service.authenticate_api_key",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(InvalidKeyError):
            await validate_request(db, "brg_revoked_xxx_yyy", str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# validate_request — validação do cliente
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inactive_client_raises_error() -> None:
    api_key = make_api_key()
    inactive_client = make_client(status=ClientStatus.PENDING)
    db = make_db(make_execute_result(scalar_result=inactive_client))

    with patch(
        "app.domains.proxy.service.authenticate_api_key",
        new=AsyncMock(return_value=api_key),
    ):
        with pytest.raises(InactiveClientError):
            await validate_request(db, "brg_xxx_yyy", str(uuid.uuid4()))


@pytest.mark.asyncio
async def test_rejected_client_raises_error() -> None:
    api_key = make_api_key()
    rejected_client = make_client(status=ClientStatus.REJECTED)
    db = make_db(make_execute_result(scalar_result=rejected_client))

    with patch(
        "app.domains.proxy.service.authenticate_api_key",
        new=AsyncMock(return_value=api_key),
    ):
        with pytest.raises(InactiveClientError):
            await validate_request(db, "brg_xxx_yyy", str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# validate_request — validação da API upstream
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disabled_api_raises_error() -> None:
    api_key = make_api_key()
    active_client = make_client()
    disabled_api = make_api(status=APIStatus.INACTIVE)
    db = make_db(make_execute_result(scalar_result=active_client))

    with patch(
        "app.domains.proxy.service.authenticate_api_key",
        new=AsyncMock(return_value=api_key),
    ):
        with patch(
            "app.domains.proxy.service.get_api_by_id",
            new=AsyncMock(return_value=disabled_api),
        ):
            with pytest.raises(DisabledAPIError):
                await validate_request(db, "brg_xxx_yyy", str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# validate_request — validação de permissão
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_active_permission_raises_error() -> None:
    api_key = make_api_key()
    active_client = make_client()
    active_api = make_api()
    db = make_db(
        make_execute_result(scalar_result=active_client),
        make_execute_result(scalar_result=None),  # sem permissão
    )

    with patch(
        "app.domains.proxy.service.authenticate_api_key",
        new=AsyncMock(return_value=api_key),
    ):
        with patch(
            "app.domains.proxy.service.get_api_by_id",
            new=AsyncMock(return_value=active_api),
        ):
            with pytest.raises(PermissionDeniedError):
                await validate_request(db, "brg_xxx_yyy", str(active_api.id))


# ---------------------------------------------------------------------------
# validate_request — rate limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_exceeded_raises_error() -> None:
    api_key = make_api_key()
    active_client = make_client()
    active_api = make_api()
    permission = make_permission(client_id=active_client.id, api_id=active_api.id)
    db = make_db(
        make_execute_result(scalar_result=active_client),
        make_execute_result(scalar_result=permission),
    )

    with patch(
        "app.domains.proxy.service.authenticate_api_key",
        new=AsyncMock(return_value=api_key),
    ):
        with patch(
            "app.domains.proxy.service.get_api_by_id",
            new=AsyncMock(return_value=active_api),
        ):
            with patch(
                "app.domains.proxy.service.check_rate_limit",
                new=AsyncMock(side_effect=RateLimitExceededError("limit exceeded")),
            ):
                with pytest.raises(RateLimitExceededError):
                    await validate_request(db, "brg_xxx_yyy", str(active_api.id))


# ---------------------------------------------------------------------------
# validate_request — caminho feliz
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_request_returns_key_client_and_api() -> None:
    api_key = make_api_key()
    active_client = make_client()
    active_api = make_api()
    permission = make_permission(client_id=active_client.id, api_id=active_api.id)
    db = make_db(
        make_execute_result(scalar_result=active_client),
        make_execute_result(scalar_result=permission),
    )

    with patch(
        "app.domains.proxy.service.authenticate_api_key",
        new=AsyncMock(return_value=api_key),
    ):
        with patch(
            "app.domains.proxy.service.get_api_by_id",
            new=AsyncMock(return_value=active_api),
        ):
            result_key, result_client, result_api = await validate_request(
                db, "brg_xxx_yyy", str(active_api.id)
            )

    assert result_key is api_key
    assert result_client is active_client
    assert result_api is active_api


# ---------------------------------------------------------------------------
# build_upstream_headers — injeção de credenciais por auth_type
# ---------------------------------------------------------------------------


def test_build_upstream_headers_for_api_key_auth() -> None:
    api = make_api(auth_type=APIAuthType.API_KEY, master_key="sk-secret-123")
    headers = build_upstream_headers(api, {"accept": "application/json"})
    assert headers["x-api-key"] == "sk-secret-123"
    assert "x-bridge-key" not in headers


def test_build_upstream_headers_for_bearer_auth() -> None:
    api = make_api(auth_type=APIAuthType.BEARER, master_key="token-xyz-789")
    headers = build_upstream_headers(api, {})
    assert headers["authorization"] == "Bearer token-xyz-789"


def test_build_upstream_headers_for_basic_auth() -> None:
    api = make_api(auth_type=APIAuthType.BASIC, master_key="user:password")
    headers = build_upstream_headers(api, {})
    assert headers["authorization"] == "Basic user:password"


def test_build_upstream_headers_for_none_auth_injects_nothing() -> None:
    api = make_api(auth_type=APIAuthType.NONE, master_key="ignored")
    headers = build_upstream_headers(api, {"x-custom": "value"})
    assert "authorization" not in headers
    assert "x-api-key" not in headers
    assert headers["x-custom"] == "value"


def test_build_upstream_headers_without_master_key_returns_filtered_only() -> None:
    api = make_api(auth_type=APIAuthType.API_KEY, master_key="")
    assert api.master_key_encrypted is None
    incoming = {"x-bridge-key": "brg_x", "accept": "application/json"}
    headers = build_upstream_headers(api, incoming)
    assert "x-bridge-key" not in headers
    assert "x-api-key" not in headers
    assert "authorization" not in headers
    assert headers["accept"] == "application/json"


def test_build_upstream_headers_strips_bridge_key() -> None:
    api = make_api(auth_type=APIAuthType.NONE, master_key="ignored")
    incoming = {
        "x-bridge-key": "brg_abcd_secret",
        "accept": "application/json",
        "content-type": "application/json",
    }
    headers = build_upstream_headers(api, incoming)
    assert "x-bridge-key" not in headers
    assert headers["accept"] == "application/json"
    assert headers["content-type"] == "application/json"


def test_build_upstream_headers_passes_through_custom_headers() -> None:
    api = make_api(auth_type=APIAuthType.NONE, master_key="ignored")
    incoming = {"x-correlation-id": "req-abc-123", "x-client-version": "2.0"}
    headers = build_upstream_headers(api, incoming)
    assert headers["x-correlation-id"] == "req-abc-123"
    assert headers["x-client-version"] == "2.0"


# ---------------------------------------------------------------------------
# forward_to_upstream — usando httpx.MockTransport
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forward_upstream_returns_upstream_response() -> None:
    api = make_api()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "ch_123"})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    response = await forward_to_upstream(
        http_client, api, "charges", "GET", {}, {}, None
    )

    assert response.status_code == 200
    assert response.json()["id"] == "ch_123"


@pytest.mark.asyncio
async def test_forward_upstream_constructs_correct_url() -> None:
    api = make_api()
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, text="ok")

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await forward_to_upstream(http_client, api, "v1/charges", "GET", {}, {}, None)

    assert "api.stripe.com" in captured["url"]
    assert "v1/charges" in captured["url"]


@pytest.mark.asyncio
async def test_forward_upstream_timeout_raises_exception() -> None:
    api = make_api()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("upstream timed out", request=request)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    with pytest.raises(httpx.TimeoutException):
        await forward_to_upstream(http_client, api, "charges", "GET", {}, {}, None)


@pytest.mark.asyncio
async def test_forward_upstream_sends_correct_method_and_body() -> None:
    api = make_api()
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["body"] = request.content
        return httpx.Response(201, json={"created": True})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await forward_to_upstream(
        http_client, api, "charges", "POST", {}, {}, b'{"amount": 1000}'
    )

    assert captured["method"] == "POST"
    assert captured["body"] == b'{"amount": 1000}'


# ---------------------------------------------------------------------------
# url_template — substituição de placeholders
# ---------------------------------------------------------------------------


def test_build_url_from_template_substitutes_query_and_token() -> None:
    api = make_api(master_key="my-token-abc", url_template="https://api.example.com/v1/{query}/{token}")
    url = _build_url_from_template(api, "search/bitcoin")
    assert url == "https://api.example.com/v1/search/bitcoin/my-token-abc"


def test_build_url_from_template_strips_leading_slash_from_query() -> None:
    api = make_api(master_key="tok", url_template="https://api.example.com/v1/{query}")
    url = _build_url_from_template(api, "/some/path")
    assert url == "https://api.example.com/v1/some/path"


def test_build_url_from_template_token_before_query() -> None:
    api = make_api(master_key="KEY123", url_template="https://api.example.com/{token}/v1/{query}")
    url = _build_url_from_template(api, "data")
    assert url == "https://api.example.com/KEY123/v1/data"


def test_build_upstream_headers_skips_header_injection_when_token_in_template() -> None:
    api = make_api(
        auth_type=APIAuthType.API_KEY,
        master_key="sk-secret",
        url_template="https://api.example.com/v1/{query}/{token}",
    )
    headers = build_upstream_headers(api, {"accept": "application/json"})
    assert "x-api-key" not in headers
    assert "authorization" not in headers
    assert headers["accept"] == "application/json"


def test_build_upstream_headers_injects_header_when_no_token_in_template() -> None:
    api = make_api(
        auth_type=APIAuthType.API_KEY,
        master_key="sk-secret",
        url_template="https://api.example.com/v1/{query}",
    )
    headers = build_upstream_headers(api, {})
    assert headers["x-api-key"] == "sk-secret"


@pytest.mark.asyncio
async def test_forward_upstream_uses_template_when_set() -> None:
    api = make_api(
        master_key="mytoken",
        url_template="https://custom.api.com/{query}/{token}",
    )
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, text="ok")

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await forward_to_upstream(http_client, api, "search/bitcoin", "GET", {}, {}, None)

    assert captured["url"] == "https://custom.api.com/search/bitcoin/mytoken"


@pytest.mark.asyncio
async def test_forward_upstream_uses_base_url_when_no_template() -> None:
    api = make_api()
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, text="ok")

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await forward_to_upstream(http_client, api, "v1/charges", "GET", {}, {}, None)

    assert "api.stripe.com" in captured["url"]
    assert "v1/charges" in captured["url"]


@pytest.mark.asyncio
async def test_forward_upstream_passes_injected_headers_to_upstream() -> None:
    api = make_api()
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, text="ok")

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await forward_to_upstream(
        http_client,
        api,
        "charges",
        "GET",
        {"x-api-key": "sk-secret-123", "accept": "application/json"},
        {},
        None,
    )

    assert captured["headers"].get("x-api-key") == "sk-secret-123"
    assert captured["headers"].get("accept") == "application/json"
