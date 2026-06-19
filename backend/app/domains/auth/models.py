import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserRole(str, Enum):
    ADMIN = "admin"  # operador da plataforma — sem account
    OWNER = "owner"  # responsável por uma account (empresa ou individual)
    MEMBER = "member"  # usuário adicional de uma empresa (feature futura)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default=UserRole.ADMIN)
    # admin da plataforma não pertence a nenhuma account
    account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("accounts.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
