"""Integration tests for the client documentation sync (sync_doc_operations).

Validates what mocks can't: upsert by (method, path) preserves the admin's
``visible`` toggle across re-syncs, and operations dropped from the spec are
removed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from app.domains.apis.models import APIAuthType, APIStatus
from app.domains.apis.service import (
    list_doc_operations,
    register_api,
    set_doc_operation_visibility,
    sync_doc_operations,
    update_api,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


def _parsed(operations: list[dict]) -> dict:
    return {
        "title": "Doc API",
        "base_url": "https://api.doc.com",
        "operations": operations,
    }


def _op(method: str, path: str, summary: str = "s") -> dict:
    return {
        "method": method,
        "path": path,
        "summary": summary,
        "description": None,
        "parameters": [],
        "request_example": None,
        "responses": [],
    }


async def _make_api(db_session: AsyncSession) -> str:
    api = await register_api(
        db_session,
        name="Doc API",
        base_url="https://api.doc.com",
        openapi_url="https://api.doc.com/openapi.json",
        status=APIStatus.ACTIVE,
    )
    return str(api.id)


async def test_sync_creates_then_upsert_preserves_visible(
    db_session: AsyncSession,
) -> None:
    api_id = await _make_api(db_session)

    spec_v1 = _parsed([_op("GET", "/people"), _op("POST", "/people")])
    with patch(
        "app.domains.apis.service.fetch_spec_docs",
        new=AsyncMock(return_value=spec_v1),
    ):
        result = await sync_doc_operations(db_session, api_id)
    assert result == {"created": 2, "updated": 0, "removed": 0, "total": 2}

    ops = await list_doc_operations(db_session, api_id)
    get_op = next(o for o in ops if o.method == "GET")
    await set_doc_operation_visibility(db_session, api_id, str(get_op.id), False)

    # Re-sync with the SAME spec: upsert, preserves the visible=False toggle.
    with patch(
        "app.domains.apis.service.fetch_spec_docs",
        new=AsyncMock(return_value=spec_v1),
    ):
        result = await sync_doc_operations(db_session, api_id)
    assert result == {"created": 0, "updated": 2, "removed": 0, "total": 2}

    ops = await list_doc_operations(db_session, api_id)
    get_op = next(o for o in ops if o.method == "GET")
    assert get_op.visible is False


async def test_sync_removes_stale_and_adds_new(db_session: AsyncSession) -> None:
    api_id = await _make_api(db_session)

    with patch(
        "app.domains.apis.service.fetch_spec_docs",
        new=AsyncMock(return_value=_parsed([_op("GET", "/a"), _op("GET", "/b")])),
    ):
        await sync_doc_operations(db_session, api_id)

    # /b removed, /c added.
    with patch(
        "app.domains.apis.service.fetch_spec_docs",
        new=AsyncMock(return_value=_parsed([_op("GET", "/a"), _op("GET", "/c")])),
    ):
        result = await sync_doc_operations(db_session, api_id)
    assert result == {"created": 1, "updated": 1, "removed": 1, "total": 2}

    paths = {o.path for o in await list_doc_operations(db_session, api_id)}
    assert paths == {"/a", "/c"}


async def test_sync_injects_master_key_when_openapi_is_protected(
    db_session: AsyncSession,
) -> None:
    api = await register_api(
        db_session,
        name="Protected Doc API",
        base_url="https://api.doc.com",
        master_key="sk-secret",
        auth_type=APIAuthType.BEARER,
        openapi_url="https://api.doc.com/openapi.json",
        status=APIStatus.ACTIVE,
    )
    mock = AsyncMock(return_value=_parsed([_op("GET", "/a")]))
    with patch("app.domains.apis.service.fetch_spec_docs", new=mock):
        await sync_doc_operations(db_session, str(api.id))

    mock.assert_awaited_once()
    # A master key (decriptada) vai como Bearer no fetch do openapi.json protegido.
    assert mock.await_args.kwargs["auth_headers"] == {
        "authorization": "Bearer sk-secret"
    }


async def test_register_api_persists_custom_docs_md(db_session: AsyncSession) -> None:
    api = await register_api(
        db_session,
        name="Custom Doc API",
        base_url="https://api.doc.com",
        custom_docs_md="# Visão geral\n\nComo usar a API.",
        status=APIStatus.ACTIVE,
    )
    assert api.custom_docs_md == "# Visão geral\n\nComo usar a API."


async def test_update_api_sets_and_clears_custom_docs_md(
    db_session: AsyncSession,
) -> None:
    api = await register_api(
        db_session,
        name="Editable Doc API",
        base_url="https://api.doc.com",
        status=APIStatus.ACTIVE,
    )
    assert api.custom_docs_md is None

    # Define
    await update_api(db_session, str(api.id), custom_docs_md="## Guia rápido")
    refreshed = await update_api(db_session, str(api.id))  # no-op re-read
    assert refreshed.custom_docs_md == "## Guia rápido"

    # Limpa com string vazia → None
    cleared = await update_api(db_session, str(api.id), custom_docs_md="")
    assert cleared.custom_docs_md is None


async def test_list_doc_operations_only_visible(db_session: AsyncSession) -> None:
    api_id = await _make_api(db_session)
    with patch(
        "app.domains.apis.service.fetch_spec_docs",
        new=AsyncMock(return_value=_parsed([_op("GET", "/x"), _op("GET", "/y")])),
    ):
        await sync_doc_operations(db_session, api_id)

    ops = await list_doc_operations(db_session, api_id)
    await set_doc_operation_visibility(db_session, api_id, str(ops[0].id), False)

    visible = await list_doc_operations(db_session, api_id, only_visible=True)
    assert len(visible) == 1
    assert visible[0].visible is True
