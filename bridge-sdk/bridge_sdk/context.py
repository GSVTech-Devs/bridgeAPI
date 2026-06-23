"""Propagação do correlation_id por toda a request via contextvars.

O correlation_id é GERADO pela Bridge e chega à API no header
``X-Correlation-Id``. A SDK o coloca num ContextVar para que todo log emitido
durante a request o herde automaticamente — sem precisar passá-lo manualmente.
"""

from __future__ import annotations

import contextlib
import uuid
from contextvars import ContextVar
from typing import Iterator, Optional

CORRELATION_HEADER = "x-correlation-id"
CLIENT_HEADER = "x-bridge-client"

_correlation_id: ContextVar[Optional[str]] = ContextVar(
    "bridge_correlation_id", default=None
)

# Cliente (account_id) da chamada atual. A Bridge o injeta via X-Bridge-Client,
# análogo ao correlation_id. Usado para resolver proxy/captcha do cliente.
_client: ContextVar[Optional[str]] = ContextVar("bridge_client", default=None)


def new_correlation_id() -> str:
    return str(uuid.uuid4())


def set_correlation_id(correlation_id: Optional[str]):
    """Define o correlation_id atual. Retorna o token para reset posterior."""
    return _correlation_id.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    return _correlation_id.get()


def reset_correlation_id(token) -> None:
    _correlation_id.reset(token)


def correlation_id_from_headers(headers, *, generate: bool = True) -> str:
    """Extrai o correlation_id de um mapa de headers (case-insensitive).

    Aceita ``starlette.datastructures.Headers`` ou ``dict``. Se ausente e
    ``generate`` for True, cria um novo (cobre chamadas que não passaram pela
    Bridge, ex.: testes locais ou health checks).
    """
    cid: Optional[str] = None
    try:
        cid = headers.get(CORRELATION_HEADER)
    except AttributeError:
        cid = None
    if not cid and isinstance(headers, dict):
        for key, value in headers.items():
            if key.lower() == CORRELATION_HEADER:
                cid = value
                break
    if not cid and generate:
        cid = new_correlation_id()
    return cid or ""


@contextlib.contextmanager
def use_correlation_id(correlation_id: str) -> Iterator[str]:
    """Context manager que define o correlation_id e o reseta ao sair."""
    token = set_correlation_id(correlation_id)
    try:
        yield correlation_id
    finally:
        reset_correlation_id(token)


# --------------------------------------------------------------------- client
def set_client(client: Optional[str]):
    """Define o cliente atual. Retorna o token para reset posterior."""
    return _client.set(client)


def get_client() -> Optional[str]:
    return _client.get()


def reset_client(token) -> None:
    _client.reset(token)


def client_from_headers(headers) -> Optional[str]:
    """Extrai o cliente (X-Bridge-Client) de um mapa de headers, case-insensitive.

    Diferente do correlation_id, NÃO gera valor quando ausente: chamadas que não
    vieram da Bridge (testes, health checks) simplesmente não têm cliente."""
    try:
        client = headers.get(CLIENT_HEADER)
    except AttributeError:
        client = None
    if not client and isinstance(headers, dict):
        for key, value in headers.items():
            if key.lower() == CLIENT_HEADER:
                client = value
                break
    return client or None


@contextlib.contextmanager
def use_client(client: str) -> Iterator[str]:
    """Context manager que define o cliente e o reseta ao sair."""
    token = set_client(client)
    try:
        yield client
    finally:
        reset_client(token)
