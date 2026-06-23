from __future__ import annotations

import pytest

from bridge_sdk import errors


def test_subclasses_are_bridge_errors() -> None:
    assert issubclass(errors.ProxyAuthFailed, errors.BridgeError)
    assert isinstance(errors.CaptchaFailed("x"), errors.BridgeError)


@pytest.mark.parametrize(
    "cls,code,http_status",
    [
        (errors.ProxyAuthFailed, "PROXY_AUTH_FAILED", 502),
        (errors.ProxyUnavailable, "PROXY_UNAVAILABLE", 503),
        (errors.CaptchaFailed, "CAPTCHA_FAILED", 502),
        (errors.CaptchaBalanceExhausted, "CAPTCHA_BALANCE_EXHAUSTED", 503),
        (errors.TargetBlocked, "TARGET_BLOCKED", 502),
        (errors.TargetTimeout, "TARGET_TIMEOUT", 504),
        (errors.InvalidQuery, "INVALID_QUERY", 400),
    ],
)
def test_error_code_and_status(cls, code, http_status) -> None:
    err = cls("boom")
    assert err.error_code == code
    assert err.http_status == http_status
    assert err.to_dict() == {"error_code": code, "message": "boom"}


def test_lookup_by_code() -> None:
    assert errors.ERRORS_BY_CODE["TARGET_TIMEOUT"] is errors.TargetTimeout


def test_default_message_is_code() -> None:
    assert errors.ProxyUnavailable().message == "PROXY_UNAVAILABLE"
