from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    app_secret_key: str = "dev-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # CORS — origens permitidas, separadas por vírgula.
    # Dev usa localhost; em produção defina CORS_ORIGINS com o domínio do front.
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,http://172.16.254.21:3000"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://bridge:bridge@localhost:5432/bridgeapi"

    # MongoDB
    mongo_url: str = (
        "mongodb://bridge:bridge@localhost:27017/bridgelogs?authSource=admin"
    )
    mongo_db: str = "bridgelogs"

    # Redis
    redis_url: str = "redis://:bridge@localhost:6379/0"

    # Rate limiting
    rate_limit_default_rpm: int = 60

    # Log retention
    log_retention_hours: int = 24
    # Retenção dos logs estruturados enviados pelas APIs (POST /ingest/logs).
    # Histórico mais longo para debug — independente do TTL dos request_logs.
    app_log_retention_days: int = 7

    # Status / readiness das APIs (POST /ingest/status)
    status_history_retention_days: int = 7
    # Após este tempo sem heartbeat, o último status é considerado defasado (stale).
    status_stale_after_seconds: int = 90
    # Intervalo de atualização do stream SSE do painel de status.
    status_stream_interval_seconds: int = 5

    # Execução híbrida do proxy (Fase 5)
    # Limite síncrono: se a upstream responder dentro disso, retorna 200 normal;
    # acima, a Bridge devolve 202 + job_id e termina em background.
    sync_timeout_s: float = 90.0
    # Timeout duro da chamada à upstream (mesmo no caminho assíncrono).
    upstream_timeout_s: float = 300.0
    # Retenção de um job (define expires_at); limpeza pode ser feita por TTL/cron.
    job_retention_hours: int = 168  # 7 dias
    # Entrega assíncrona (5b)
    job_stream_interval_seconds: float = 2.0   # poll do SSE GET /jobs/{id}/stream
    job_stream_max_seconds: float = 600.0      # corta o stream após este tempo
    webhook_max_attempts: int = 3              # tentativas de POST no callback
    webhook_timeout_s: float = 10.0
    # Segredo p/ assinar o webhook (HMAC-SHA256). Default: app_secret_key.
    webhook_signing_secret: str = ""

    # Alertas (Fase 6): limiar de saldo de captcha p/ alerta de saldo baixo.
    captcha_low_balance_threshold_usd: float = 5.0

    # Encryption
    encryption_key: str = "0" * 64


settings = Settings()
