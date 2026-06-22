from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AccountRole(Base):
    """Papel customizado de uma account (empresa).

    O owner cria roles de nome livre (ex.: "dev", "financeiro") e define em
    ``capabilities`` o conjunto de features de dashboard que os membros daquela
    role podem acessar. As capabilities válidas são as de
    ``app.core.authz.ASSIGNABLE_FEATURES``.
    """

    __tablename__ = "account_roles"
    __table_args__ = (
        UniqueConstraint("account_id", "name", name="uq_account_role_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
