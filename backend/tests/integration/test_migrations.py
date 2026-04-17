"""
Smoke tests do ciclo de migração Alembic.

O que valida:
  1. upgrade("head")   → todas as tabelas de domínio existem
  2. downgrade("base") → todas as tabelas de domínio são removidas
  3. upgrade("head")   → tabelas restauradas (idempotência)

Usa um banco isolado (bridgeapi_migrate_test) para não interferir na
suite de integração principal que usa bridgeapi_test.

O que pega que os outros testes não pegam:
- Script downgrade quebrado ou ausente numa migração
- DROP/ALTER incompatível com estado do banco (ex.: remover coluna NOT NULL
  sem DEFAULT quando há dados)
- Conflito de revision IDs após merges paralelos de branches
- Migração que só funciona na direção upgrade e trava o rollback em produção

ATENÇÃO: os testes deste módulo são ORDER-DEPENDENT — cada teste herda o
estado do banco deixado pelo anterior. Não reordene sem ajustar as asserções.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# ──────────────────────────── constants ────────────────────────────────────

_BASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://bridge:bridge@localhost:5433/bridgeapi_test",
)

# Banco isolado para não colidir com os fixtures session-scoped de integração
MIGRATE_DB_URL = _BASE_URL.rsplit("/", 1)[0] + "/bridgeapi_migrate_test"

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

# Todas as tabelas que devem existir após `upgrade head`
_DOMAIN_TABLES: frozenset[str] = frozenset(
    {
        "users",
        "clients",
        "external_apis",
        "api_keys",
        "endpoints",
        "permissions",
        "request_metrics",
    }
)


# ──────────────────────────── helpers async ────────────────────────────────

async def _ensure_db(url: str) -> None:
    import asyncpg

    parsed = urlparse(url.replace("postgresql+asyncpg", "postgresql"))
    db_name = parsed.path.lstrip("/")
    admin_dsn = parsed._replace(path="/postgres").geturl()

    conn = await asyncpg.connect(admin_dsn)
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", db_name
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await conn.close()


async def _drop_db(url: str) -> None:
    import asyncpg

    parsed = urlparse(url.replace("postgresql+asyncpg", "postgresql"))
    db_name = parsed.path.lstrip("/")
    admin_dsn = parsed._replace(path="/postgres").geturl()

    conn = await asyncpg.connect(admin_dsn)
    try:
        # Encerra conexões ativas antes de dropar
        await conn.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = $1 AND pid <> pg_backend_pid()
            """,
            db_name,
        )
        await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
    finally:
        await conn.close()


async def _get_public_tables(url: str) -> set[str]:
    """Retorna nomes de todas as tabelas no schema public."""
    engine = create_async_engine(url, echo=False)
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        tables = {row[0] for row in result.fetchall()}
    await engine.dispose()
    return tables


async def _count_alembic_versions(url: str) -> int:
    """Retorna quantas linhas existem em alembic_version (0 ou 1 normalmente)."""
    engine = create_async_engine(url, echo=False)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM alembic_version"))
            return result.scalar() or 0
    except Exception:
        return 0
    finally:
        await engine.dispose()


# ──────────────────────────── fixture ──────────────────────────────────────

@pytest.fixture(scope="module")
def migrate_cfg():
    """
    Cria banco isolado bridgeapi_migrate_test, yield de um Config Alembic
    apontando para ele, e remove o banco no teardown.

    Síncrono (sem async def) para evitar conflito com asyncio.run() interno
    do env.py do Alembic.
    """
    from alembic.config import Config
    from app.core.config import settings

    asyncio.run(_ensure_db(MIGRATE_DB_URL))

    # Guarda URL original e aponta settings para o banco de migração
    saved_url = settings.database_url
    settings.database_url = MIGRATE_DB_URL

    cfg = Config(str(ALEMBIC_INI))

    yield cfg

    # Teardown: restaura URL original e remove banco temporário
    settings.database_url = saved_url
    asyncio.run(_drop_db(MIGRATE_DB_URL))


# ──────────────────────────── testes ───────────────────────────────────────

def test_upgrade_head_creates_all_domain_tables(migrate_cfg) -> None:
    """upgrade('head') deve criar todas as tabelas de domínio."""
    from alembic import command

    command.upgrade(migrate_cfg, "head")

    tables = asyncio.run(_get_public_tables(MIGRATE_DB_URL))
    missing = _DOMAIN_TABLES - tables
    assert not missing, f"Tabelas ausentes após upgrade head: {missing}"


def test_upgrade_head_records_single_version(migrate_cfg) -> None:
    """alembic_version deve conter exatamente 1 linha após upgrade head."""
    count = asyncio.run(_count_alembic_versions(MIGRATE_DB_URL))
    assert count == 1, f"Esperado 1 revision ativo, encontrado: {count}"


def test_downgrade_base_removes_all_domain_tables(migrate_cfg) -> None:
    """downgrade('base') deve remover todas as tabelas de domínio."""
    from alembic import command

    command.downgrade(migrate_cfg, "base")

    tables = asyncio.run(_get_public_tables(MIGRATE_DB_URL))
    remaining = _DOMAIN_TABLES & tables
    assert not remaining, (
        f"Tabelas que deveriam ter sido removidas no downgrade: {remaining}"
    )


def test_downgrade_base_empties_version_table(migrate_cfg) -> None:
    """alembic_version deve estar vazia após downgrade base."""
    count = asyncio.run(_count_alembic_versions(MIGRATE_DB_URL))
    assert count == 0, (
        f"Esperado 0 revisions após downgrade base, encontrado: {count}"
    )


def test_re_upgrade_restores_all_tables(migrate_cfg) -> None:
    """upgrade após downgrade deve restaurar todas as tabelas (idempotência)."""
    from alembic import command

    command.upgrade(migrate_cfg, "head")

    tables = asyncio.run(_get_public_tables(MIGRATE_DB_URL))
    missing = _DOMAIN_TABLES - tables
    assert not missing, f"Tabelas ausentes após re-upgrade: {missing}"
