from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AccountType(str, Enum):
    COMPANY = "company"
    INDIVIDUAL = "individual"


class AccountStatus(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"


class Account(Base):
    """Entidade consumidora — dona de chaves, permissões e métricas.

    Sucede a antiga tabela ``clients``. Pode ser uma empresa (com vários
    usuários) ou uma conta individual (um único usuário avulso).
    """

    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(
        String(20), default=AccountType.INDIVIDUAL, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default=AccountStatus.ACTIVE, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
