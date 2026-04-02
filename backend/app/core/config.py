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

    # Encryption
    encryption_key: str = "0" * 64


settings = Settings()
