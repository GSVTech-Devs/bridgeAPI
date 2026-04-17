# RED → GREEN
# Testes unitários para app/domains/apis/service.py.
# A AsyncSession é mockada diretamente para cobrir a lógica de negócio
# sem necessidade de banco de dados real.
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domains.apis.models import (
    APIAuthType,
    APIStatus,
    Endpoint,
    ExternalAPI,
    HTTPMethod,
)
from app.domains.apis.service import (
    APINotFoundError,
    DuplicateAPINameError,
    DuplicateSlugError,
    add_endpoint,
    disable_api,
    enable_api,
    get_api_by_id,
    get_api_by_slug,
    list_apis,
    list_endpoints_for_api,
    register_api,
)


def make_api(status: APIStatus = APIStatus.ACTIVE) -> ExternalAPI:
    return ExternalAPI(
        id=uuid.uuid4(),
        name="Stripe API",
        base_url="https://api.stripe.com",
        master_key_encrypted="encrypted-key",
        auth_type=APIAuthType.API_KEY,
        status=status,
        created_at=datetime.now(timezone.utc),
    )


def make_endpoint(api_id: uuid.UUID | None = None) -> Endpoint:
    return Endpoint(
        id=uuid.uuid4(),
        api_id=api_id or uuid.uuid4(),
        method=HTTPMethod.GET,
        path="/charges",
        status="active",
        cost_rule=None,
        created_at=datetime.now(timezone.utc),
    )


def make_db(scalar_result=None, scalars_result=None, count_result=0) -> AsyncMock:
    """Constrói um mock de AsyncSession com resultado configurável."""
    db = AsyncMock()
    db.add = MagicMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = scalar_result
    execute_result.scalar_one.return_value = count_result
    execute_result.scalars.return_value.all.return_value = scalars_result or []
    db.execute.return_value = execute_result
    return db


def make_db_seq(*scalar_results) -> AsyncMock:
    """Constrói um mock que retorna resultados diferentes a cada execute() chamado."""
    db = AsyncMock()
    db.add = MagicMock()
    results = []
    for r in scalar_results:
        m = MagicMock()
        m.scalar_one_or_none.return_value = r
        m.scalar_one.return_value = 0
        m.scalars.return_value.all.return_value = []
        results.append(m)
    db.execute.side_effect = results
    return db


# ---------------------------------------------------------------------------
# register_api
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_register_api() -> None:
    db = make_db(scalar_result=None)
    await register_api(
        db,
        name="Stripe API",
        base_url="https://api.stripe.com",
        master_key="sk-secret",
        auth_type=APIAuthType.API_KEY,
    )
    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_master_key_is_stored_encrypted() -> None:
    db = make_db(scalar_result=None)
    plain_key = "sk-plaintext-secret"
    await register_api(
        db,
        name="Stripe API",
        base_url="https://api.stripe.com",
        master_key=plain_key,
        auth_type=APIAuthType.API_KEY,
    )
    added_api: ExternalAPI = db.add.call_args[0][0]
    assert added_api.master_key_encrypted is not None
    assert added_api.master_key_encrypted != plain_key


@pytest.mark.asyncio
async def test_duplicate_api_name_raises_error() -> None:
    db = make_db(scalar_result=make_api())  # nome já existe
    with pytest.raises(DuplicateAPINameError):
        await register_api(db, name="Stripe API", base_url="https://api.stripe.com")


@pytest.mark.asyncio
async def test_register_api_without_master_key() -> None:
    db = make_db(scalar_result=None)
    await register_api(db, name="Open API", base_url="https://open.example.com")
    added_api: ExternalAPI = db.add.call_args[0][0]
    assert added_api.master_key_encrypted is None


# ---------------------------------------------------------------------------
# list_apis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_apis_returns_apis_and_total() -> None:
    apis = [make_api(), make_api()]
    db = make_db(scalars_result=apis, count_result=2)
    result, total = await list_apis(db)
    assert total == 2
    assert len(result) == 2


# ---------------------------------------------------------------------------
# get_api_by_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_api_by_id_returns_api() -> None:
    api = make_api()
    db = make_db(scalar_result=api)
    result = await get_api_by_id(db, str(api.id))
    assert result is api


@pytest.mark.asyncio
async def test_get_api_by_id_raises_not_found() -> None:
    db = make_db(scalar_result=None)
    with pytest.raises(APINotFoundError):
        await get_api_by_id(db, str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# add_endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_add_endpoint_to_api() -> None:
    api = make_api()
    db = make_db(scalar_result=api)
    await add_endpoint(db, api_id=str(api.id), method=HTTPMethod.GET, path="/charges")
    db.add.assert_called_once()
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_add_endpoint_to_nonexistent_api_raises_not_found() -> None:
    db = make_db(scalar_result=None)
    with pytest.raises(APINotFoundError):
        await add_endpoint(
            db, api_id=str(uuid.uuid4()), method=HTTPMethod.POST, path="/payments"
        )


@pytest.mark.asyncio
async def test_list_endpoints_for_api_returns_only_api_endpoints() -> None:
    api = make_api()
    endpoints = [make_endpoint(api.id), make_endpoint(api.id)]
    db = make_db(scalars_result=endpoints)
    result = await list_endpoints_for_api(db, api.id)
    assert len(result) == 2
    assert result[0].api_id == api.id


# ---------------------------------------------------------------------------
# disable_api / enable_api
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_disable_api() -> None:
    api = make_api(APIStatus.ACTIVE)
    db = make_db(scalar_result=api)
    await disable_api(db, str(api.id))
    assert api.status == APIStatus.INACTIVE
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_admin_can_enable_api() -> None:
    api = make_api(APIStatus.INACTIVE)
    db = make_db(scalar_result=api)
    await enable_api(db, str(api.id))
    assert api.status == APIStatus.ACTIVE
    db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# register_api — slug
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_api_stores_slug() -> None:
    # name check → None, slug check → None
    db = make_db_seq(None, None)
    await register_api(db, name="Finance API", base_url="https://api.example.com", slug="finance")
    added_api: ExternalAPI = db.add.call_args[0][0]
    assert added_api.slug == "finance"


@pytest.mark.asyncio
async def test_register_api_without_slug_stores_none() -> None:
    db = make_db(scalar_result=None)
    await register_api(db, name="Finance API", base_url="https://api.example.com")
    added_api: ExternalAPI = db.add.call_args[0][0]
    assert added_api.slug is None


@pytest.mark.asyncio
async def test_duplicate_slug_raises_error() -> None:
    existing = make_api()
    # name check → None (name free), slug check → existing (slug taken)
    db = make_db_seq(None, existing)
    with pytest.raises(DuplicateSlugError):
        await register_api(
            db, name="New API", base_url="https://api.example.com", slug="taken-slug"
        )


@pytest.mark.asyncio
async def test_duplicate_name_checked_before_slug() -> None:
    existing = make_api()
    # name check → existing (name taken) — slug check never reached
    db = make_db_seq(existing)
    with pytest.raises(DuplicateAPINameError):
        await register_api(
            db, name="Stripe API", base_url="https://api.example.com", slug="finance"
        )


# ---------------------------------------------------------------------------
# get_api_by_slug
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_api_by_slug_returns_api() -> None:
    api = make_api()
    api.slug = "finance"
    db = make_db(scalar_result=api)
    result = await get_api_by_slug(db, "finance")
    assert result is api


@pytest.mark.asyncio
async def test_get_api_by_slug_raises_not_found() -> None:
    db = make_db(scalar_result=None)
    with pytest.raises(APINotFoundError):
        await get_api_by_slug(db, "nonexistent")


@pytest.mark.asyncio
async def test_disabled_api_still_retrievable() -> None:
    api = make_api(APIStatus.INACTIVE)
    db = make_db(scalar_result=api)
    result = await get_api_by_id(db, str(api.id))
    assert result.status == APIStatus.INACTIVE
