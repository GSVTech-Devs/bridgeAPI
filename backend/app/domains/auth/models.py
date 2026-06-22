import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserRole(str, Enum):
    ADMIN = "admin"  # operador da plataforma — sem account
    OWNER = "owner"  # responsável por uma account (empresa ou individual)
    MEMBER = "member"  # usuário adicional de uma empresa (feature futura)


class User(Base):
    """Vínculo de uma pessoa a uma account.

    O email **não** é globalmente único: a mesma pessoa pode ter acesso a
    várias accounts (empresas) e, para cada uma, existe uma linha ``User``
    própria (com seu ``account_id``/``role``/``role_id``). Esse email funciona
    como uma identidade única — todas as linhas que o compartilham mantêm o
    mesmo ``password_hash`` ("um email, uma senha"). A unicidade real é por
    ``(email, account_id)``: um email no máximo uma vez em cada account.
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", "account_id", name="uq_user_email_account"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default=UserRole.ADMIN)
    # admin da plataforma não pertence a nenhuma account
    account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("accounts.id"), nullable=True, index=True
    )
    # role customizada da empresa (apenas para membros); owner/admin não usam.
    role_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("account_roles.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
