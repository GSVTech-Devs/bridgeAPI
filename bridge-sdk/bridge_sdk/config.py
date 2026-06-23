"""Configuração da SDK."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class SDKConfig:
    # Obrigatórios
    platform_url: str          # base da Bridge, ex.: https://bridge.example.com
    service_token: str         # token de serviço da API (header X-Service-Token)

    # Identidade
    api_version: str = "unknown"

    # Comportamento de envio
    enabled: bool = True       # se False, não envia para a plataforma (só echo local)
    local_echo: bool = True    # também imprime cada log como JSON no stdout
    flush_interval: float = 2.0   # segundos entre flushes do buffer
    batch_max: int = 100          # máximo de entries por requisição
    buffer_max: int = 10_000      # capacidade do buffer (descarta os mais antigos ao encher)
    timeout: float = 5.0          # timeout HTTP do envio
    max_retries: int = 3          # tentativas extras antes do fallback local
    retry_base_delay: float = 0.5  # backoff exponencial inicial

    # Heartbeat de status (readiness) → POST /ingest/status
    status_enabled: bool = True
    status_interval: float = 30.0  # segundos entre relatórios de status

    # Cliente de proxy → GET /ingest/proxies
    proxy_cache_ttl: float = 60.0  # segundos de cache da config do pool

    @classmethod
    def from_env(cls, **overrides) -> "SDKConfig":
        """Monta a config a partir de variáveis de ambiente, com overrides opcionais.

        Lê: BRIDGE_PLATFORM_URL, BRIDGE_SERVICE_TOKEN, BRIDGE_API_VERSION.
        """
        data = {
            "platform_url": os.environ.get("BRIDGE_PLATFORM_URL", ""),
            "service_token": os.environ.get("BRIDGE_SERVICE_TOKEN", ""),
            "api_version": os.environ.get("BRIDGE_API_VERSION", "unknown"),
        }
        data.update(overrides)
        if not data["platform_url"] or not data["service_token"]:
            raise ValueError(
                "platform_url e service_token são obrigatórios "
                "(defina BRIDGE_PLATFORM_URL e BRIDGE_SERVICE_TOKEN ou passe overrides)."
            )
        return cls(**data)
