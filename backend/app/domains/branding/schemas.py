from __future__ import annotations

from pydantic import BaseModel


class BrandingResponse(BaseModel):
    """Identidade visual efetiva da conta (consumida pela UI do portal)."""

    # Logo personalizada como data URI (``data:<mime>;base64,...``) ou ``None``
    # quando a conta ainda usa a marca padrão.
    logo_data_uri: str | None = None
