from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.domains.clients.models import Client, ClientStatus


class DuplicateEmailError(Exception):
    pass


class ClientNotFoundError(Exception):
    pass


class InvalidStatusTransitionError(Exception):
    pass


async def register_client(
    db: AsyncSession, name: str, email: str, password: str
) -> Client:
    existing = await db.execute(select(Client).where(Client.email == email))
    if existing.scalar_one_or_none() is not None:
        raise DuplicateEmailError(f"Email already registered: {email}")

    client = Client(name=name, email=email, password_hash=hash_password(password))
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client


async def list_clients(
    db: AsyncSession, page: int = 1, per_page: int = 20
) -> tuple[list[Client], int]:
    total_result = await db.execute(select(func.count()).select_from(Client))
    total = total_result.scalar_one()

    result = await db.execute(
        select(Client).offset((page - 1) * per_page).limit(per_page)
    )
    return list(result.scalars().all()), total


async def get_client_by_id(db: AsyncSession, client_id: str) -> Client:
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        raise ClientNotFoundError(f"Client not found: {client_id}")
    return client


async def approve_client(db: AsyncSession, client_id: str) -> Client:
    client = await get_client_by_id(db, client_id)
    if client.status != ClientStatus.PENDING:
        raise InvalidStatusTransitionError(
            f"Cannot approve client with status: {client.status}"
        )
    client.status = ClientStatus.ACTIVE
    await db.commit()
    await db.refresh(client)
    return client


async def reject_client(db: AsyncSession, client_id: str) -> Client:
    client = await get_client_by_id(db, client_id)
    if client.status == ClientStatus.REJECTED:
        raise InvalidStatusTransitionError("Client is already rejected")
    client.status = ClientStatus.REJECTED
    await db.commit()
    await db.refresh(client)
    return client


async def authenticate_client(
    db: AsyncSession, email: str, password: str
) -> Client | None:
    result = await db.execute(select(Client).where(Client.email == email))
    client = result.scalar_one_or_none()
    if client is None or not verify_password(password, client.password_hash):
        return None
    return client
