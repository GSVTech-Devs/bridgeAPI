from __future__ import annotations

import base64

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.accounts.models import Account
from app.domains.accounts.service import get_account_by_id

# ---------------------------------------------------------------------------
# Política de upload da logo — espelhada em frontend/src/lib/branding.ts.
# ---------------------------------------------------------------------------
MAX_LOGO_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_LOGO_TYPES: tuple[str, ...] = ("image/png", "image/jpeg", "image/webp")
LOGO_REQUIREMENTS_MESSAGE = (
    "Envie PNG, JPG ou WEBP de até 5 MB "
    "(recomendado ~320×80 px, fundo transparente)."
)


class InvalidLogoError(Exception):
    """Upload de logo rejeitado pela validação (formato/tamanho/conteúdo)."""


def _content_matches(content_type: str, data: bytes) -> bool:
    """Confere os *magic bytes* do arquivo contra o mime type declarado.

    Evita que um arquivo arbitrário se passe por imagem só trocando o
    ``Content-Type`` do upload.
    """
    if content_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if content_type == "image/webp":
        return len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def validate_logo(content_type: str | None, data: bytes) -> str:
    """Valida formato, tamanho e conteúdo da logo. Retorna o mime normalizado.

    Levanta ``InvalidLogoError`` com mensagem amigável quando algo não bate.
    """
    if not data:
        raise InvalidLogoError("Arquivo vazio.")
    if len(data) > MAX_LOGO_BYTES:
        raise InvalidLogoError("Arquivo muito grande. O limite é 5 MB.")
    normalized = (content_type or "").split(";")[0].strip().lower()
    if normalized not in ALLOWED_LOGO_TYPES:
        raise InvalidLogoError("Formato inválido. Envie PNG, JPG ou WEBP.")
    if not _content_matches(normalized, data):
        raise InvalidLogoError(
            "O conteúdo do arquivo não corresponde a uma imagem "
            "PNG, JPG ou WEBP válida."
        )
    return normalized


def logo_data_uri(account: Account) -> str | None:
    """Monta o data URI da logo da conta (ou ``None`` se não houver)."""
    if account.logo_data and account.logo_content_type:
        encoded = base64.b64encode(account.logo_data).decode("ascii")
        return f"data:{account.logo_content_type};base64,{encoded}"
    return None


async def set_account_logo(
    db: AsyncSession, account_id: str, *, content_type: str, data: bytes
) -> Account:
    account = await get_account_by_id(db, account_id)
    account.logo_data = data
    account.logo_content_type = content_type
    await db.commit()
    await db.refresh(account)
    return account


async def clear_account_logo(db: AsyncSession, account_id: str) -> Account:
    account = await get_account_by_id(db, account_id)
    account.logo_data = None
    account.logo_content_type = None
    await db.commit()
    await db.refresh(account)
    return account
