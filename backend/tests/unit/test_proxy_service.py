# Testes unitários para app/domains/proxy/service.py.
# Cobre a pipeline de validação, injeção de headers e forwarding.
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.security import encrypt_value
from app.domains.accounts.models import Account, AccountStatus, AccountType
from app.domains.apis.models import APIAuthType, APIStatus, ExternalAPI
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


def make_api_key(
    status: APIKeyStatus = APIKeyStatus.ACTIVE,
    account_id: uuid.UUID | None = None,
    api_id: uuid.UUID | None = None,
) -> APIKey:
    return APIKey(
        id=uuid.uuid4(),
        account_id=account_id or uuid.uuid4(),
        api_id=api_id,
        name="Test Key",
        key_prefix="abcd1234",
        key_secret_hash="hashed",
        status=status,
        created_at=datetime.now(timezone.utc),
    )


def make_account(status: AccountStatus = AccountStatus.ACTIVE) -> Account:
    return Account(
        id=uuid.uuid4(),
        name="Acme Corp",
        type=AccountType.INDIVIDUAL,
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
    account_id: uuid.UUID | None = None,
    api_id: uuid.UUID | None = None,
) -> Permission:
    return Permission(
        id=uuid.uuid4(),
        account_id=account_id or uuid.uuid4(),
        api_id=api_id or uuid.uuid4(),
        granted_at=datetime.now(timezone.utc),
        revoked_at=None,
    )


def make_execute_result(scalar_result=None) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_result
    return result


def make_db(*results: MagicMock) -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.side_effect = list(results)
    return db


# ---------------------------------------------------------------------------
# validate_request
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
async def test_inactive_account_raises_error() -> None:
    api_key = make_api_key()
    blocked = make_account(status=AccountStatus.BLOCKED)
    db = make_db(make_execute_result(scalar_result=blocked))

    with patch(
        "app.domains.proxy.service.authenticate_api_key",
        new=AsyncMock(return_value=api_key),
    ):
        with pytest.raises(InactiveClientError):
            await validate_request(db, "brg_xxx_yyy", str(uuid.uuid4()))


@pytest.mark.asyncio
async def test_key_bound_to_different_api_raises_permission_denied() -> None:
    bound_api_id = uuid.uuid4()
    requested_api_id = uuid.uuid4()
    api_key = make_api_key(api_id=bound_api_id)
    db = make_db(make_execute_result(scalar_result=make_account()))

    with patch(
        "app.domains.proxy.service.authenticate_api_key",
        new=AsyncMock(return_value=api_key),
    ):
        with pytest.raises(PermissionDeniedError):
            await validate_request(db, "brg_xxx_yyy", str(requested_api_id))


@pytest.mark.asyncio
async def test_disabled_api_raises_error() -> None:
    api_key = make_api_key()
    disabled_api = make_api(status=APIStatus.INACTIVE)
    db = make_db(make_execute_result(scalar_result=make_account()))

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


@pytest.mark.asyncio
async def test_no_active_permission_raises_error() -> None:
    api_key = make_api_key()
    active_api = make_api()
    db = make_db(
        make_execute_result(scalar_result=make_account()),
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


@pytest.mark.asyncio
async def test_rate_limit_exceeded_raises_error() -> None:
    api_key = make_api_key()
    account = make_account()
    active_api = make_api()
    permission = make_permission(account_id=account.id, api_id=active_api.id)
    db = make_db(
        make_execute_result(scalar_result=account),
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


@pytest.mark.asyncio
async def test_valid_request_returns_key_account_and_api() -> None:
    api_key = make_api_key()
    account = make_account()
    active_api = make_api()
    permission = make_permission(account_id=account.id, api_id=active_api.id)
    db = make_db(
        make_execute_result(scalar_result=account),
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
            result_key, result_account, result_api = await validate_request(
                db, "brg_xxx_yyy", str(active_api.id)
            )

    assert result_key is api_key
    assert result_account is account
    assert result_api is active_api


# ---------------------------------------------------------------------------
# build_upstream_headers
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


def test_build_upstream_headers_strips_bridge_key() -> None:
    api = make_api(auth_type=APIAuthType.NONE, master_key="ignored")
    incoming = {"x-bridge-key": "brg_abcd_secret", "accept": "application/json"}
    headers = build_upstream_headers(api, incoming)
    assert "x-bridge-key" not in headers
    assert headers["accept"] == "application/json"


def test_build_upstream_headers_skips_injection_when_token_in_template() -> None:
    api = make_api(
        auth_type=APIAuthType.API_KEY,
        master_key="sk-secret",
        url_template="https://api.example.com/v1/{query}/{token}",
    )
    headers = build_upstream_headers(api, {"accept": "application/json"})
    assert "x-api-key" not in headers


# ---------------------------------------------------------------------------
# url_template / forward_to_upstream
# ---------------------------------------------------------------------------


def test_build_url_from_template_substitutes_query_and_token() -> None:
    api = make_api(
        master_key="my-token-abc",
        url_template="https://api.example.com/v1/{query}/{token}",
    )
    url = _build_url_from_template(api, "search/bitcoin")
    assert url == "https://api.example.com/v1/search/bitcoin/my-token-abc"


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
async def test_forward_upstream_uses_template_when_set() -> None:
    api = make_api(
        master_key="mytoken", url_template="https://custom.api.com/{query}/{token}"
    )
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, text="ok")

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await forward_to_upstream(http_client, api, "search/bitcoin", "GET", {}, {}, None)

    assert captured["url"] == "https://custom.api.com/search/bitcoin/mytoken"


@pytest.mark.asyncio
async def test_forward_upstream_timeout_raises_exception() -> None:
    api = make_api()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("upstream timed out", request=request)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.TimeoutException):
        await forward_to_upstream(http_client, api, "charges", "GET", {}, {}, None)
