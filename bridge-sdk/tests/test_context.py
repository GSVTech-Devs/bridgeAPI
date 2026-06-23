from __future__ import annotations

import uuid

from bridge_sdk import context


def setup_function() -> None:
    # isola cada teste — limpa o correlation_id do contexto
    context.set_correlation_id(None)


def test_set_and_get_round_trip() -> None:
    cid = str(uuid.uuid4())
    context.set_correlation_id(cid)
    assert context.get_correlation_id() == cid


def test_use_correlation_id_resets_on_exit() -> None:
    with context.use_correlation_id("temp-cid"):
        assert context.get_correlation_id() == "temp-cid"
    assert context.get_correlation_id() is None


def test_from_headers_uses_provided_value() -> None:
    cid = str(uuid.uuid4())
    assert context.correlation_id_from_headers({"X-Correlation-Id": cid}) == cid


def test_from_headers_is_case_insensitive() -> None:
    cid = str(uuid.uuid4())
    assert context.correlation_id_from_headers({"x-correlation-id": cid}) == cid


def test_from_headers_generates_when_missing() -> None:
    generated = context.correlation_id_from_headers({"accept": "application/json"})
    assert uuid.UUID(generated)  # é um UUID válido


def test_from_headers_no_generate_returns_empty() -> None:
    assert context.correlation_id_from_headers({}, generate=False) == ""
