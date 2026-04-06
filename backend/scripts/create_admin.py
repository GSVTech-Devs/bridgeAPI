#!/usr/bin/env python
"""
Cria um usuário admin no banco de dados.

Uso:
    python scripts/create_admin.py --email admin@bridge.dev --password suasenha

O script deve ser executado a partir do diretório backend/ com o ambiente
virtual ativado e as variáveis de ambiente do .env carregadas.

    cd backend
    python scripts/create_admin.py --email admin@bridge.dev --password suasenha
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Garante que o pacote app é encontrado quando rodado de backend/
sys.path.insert(0, ".")

from app.core.config import settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.domains.auth.models import User  # noqa: E402


async def create_admin(email: str, password: str) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Verifica se já existe
        result = await session.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"[!] Usuário '{email}' já existe (role={existing.role}).")
            await engine.dispose()
            return

        user = User(
            email=email,
            password_hash=hash_password(password),
            role="admin",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    await engine.dispose()
    print(f"[✓] Admin criado com sucesso!")
    print(f"    Email : {user.email}")
    print(f"    ID    : {user.id}")
    print(f"    Role  : {user.role}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria um usuário admin no Bridge API")
    parser.add_argument("--email", required=True, help="Email do admin")
    parser.add_argument("--password", required=True, help="Senha do admin")
    args = parser.parse_args()

    if len(args.password) < 8:
        print("[!] Erro: a senha deve ter pelo menos 8 caracteres.")
        sys.exit(1)

    asyncio.run(create_admin(args.email, args.password))


if __name__ == "__main__":
    main()
