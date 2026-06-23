"""Taxonomia de erros estruturados compartilhada entre as APIs e a Bridge.

Cada erro carrega um ``error_code`` estável e um ``http_status`` sugerido. A API
levanta a subclasse apropriada; o gateway mapeia o code para status + mensagem
clara ao cliente, e o code aparece nos logs (facilita filtrar por causa raiz).
"""

from __future__ import annotations


class BridgeError(Exception):
    """Base de todos os erros conhecidos do contrato Bridge."""

    error_code: str = "BRIDGE_ERROR"
    http_status: int = 502

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.error_code)
        self.message = message or self.error_code

    def to_dict(self) -> dict:
        return {"error_code": self.error_code, "message": self.message}


class ProxyAuthFailed(BridgeError):
    error_code = "PROXY_AUTH_FAILED"
    http_status = 502


class ProxyUnavailable(BridgeError):
    error_code = "PROXY_UNAVAILABLE"
    http_status = 503


class CaptchaFailed(BridgeError):
    error_code = "CAPTCHA_FAILED"
    http_status = 502


class CaptchaBalanceExhausted(BridgeError):
    error_code = "CAPTCHA_BALANCE_EXHAUSTED"
    http_status = 503


class TargetBlocked(BridgeError):
    error_code = "TARGET_BLOCKED"
    http_status = 502


class TargetTimeout(BridgeError):
    error_code = "TARGET_TIMEOUT"
    http_status = 504


class InvalidQuery(BridgeError):
    error_code = "INVALID_QUERY"
    http_status = 400


# Lookup por code — útil no gateway para reconstruir/encaminhar o erro.
ERRORS_BY_CODE: dict[str, type[BridgeError]] = {
    cls.error_code: cls
    for cls in (
        ProxyAuthFailed,
        ProxyUnavailable,
        CaptchaFailed,
        CaptchaBalanceExhausted,
        TargetBlocked,
        TargetTimeout,
        InvalidQuery,
    )
}
