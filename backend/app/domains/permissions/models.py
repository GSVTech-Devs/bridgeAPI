from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Permission(Base):
    __tablename__ = "permissions"
    __table_args__ = (
        UniqueConstraint("account_id", "api_id", name="uq_permission_account_api"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    api_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_apis.id"), index=True
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    # Admin liberou o cliente a configurar o PRÓPRIO proxy desta API? Se sim, a
    # Bridge usa os proxies do cliente (ele começa sem nenhum e configura os dele).
    proxy_managed_by_client: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    # Idem para captcha: cliente configura o próprio provedor desta API?
    captcha_managed_by_client: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
