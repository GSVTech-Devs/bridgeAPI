# Garante que o correlation_id é propagado à API downstream via X-Correlation-Id.
from __future__ import annotations

import uuid

from app.domains.apis.models import ExternalAPI
from app.domains.proxy.service import build_upstream_headers


def make_api() -> ExternalAPI:
    api = ExternalAPI(name=f"api-{uuid.uuid4()}", base_url="https://up.example.com")
    api.master_key_encrypted = None
    api.url_template = None
    return api


def test_correlation_id_is_injected_when_provided() -> None:
    cid = str(uuid.uuid4())
    headers = build_upstream_headers(make_api(), {"accept": "application/json"}, cid)
    assert headers["x-correlation-id"] == cid


def test_correlation_id_overrides_client_supplied_value() -> None:
    cid = str(uuid.uuid4())
    headers = build_upstream_headers(
        make_api(), {"x-correlation-id": "forged-by-client"}, cid
    )
    assert headers["x-correlation-id"] == cid


def test_no_correlation_header_when_not_provided() -> None:
    headers = build_upstream_headers(make_api(), {"accept": "application/json"})
    assert "x-correlation-id" not in headers
