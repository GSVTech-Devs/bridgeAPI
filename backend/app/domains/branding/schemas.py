from __future__ import annotations

from pydantic import BaseModel, Field

_HEX = r"^#[0-9a-fA-F]{6}$"


class BrandModeColors(BaseModel):
    """Cores de um modo (claro ou escuro). Cada slot é opcional (``None`` = padrão)."""

    primary: str | None = Field(None, pattern=_HEX)
    secondary: str | None = Field(None, pattern=_HEX)
    tertiary: str | None = Field(None, pattern=_HEX)
    background: str | None = Field(None, pattern=_HEX)


class BrandTheme(BaseModel):
    """Tema de marca completo: paleta para o modo claro e para o escuro."""

    light: BrandModeColors = BrandModeColors()
    dark: BrandModeColors = BrandModeColors()


class BrandingResponse(BaseModel):
    """Identidade visual efetiva da conta (consumida pela UI do portal)."""

    # Logo personalizada como data URI (``data:<mime>;base64,...``) ou ``None``
    # quando a conta ainda usa a marca padrão.
    logo_data_uri: str | None = None
    # Tema de marca por modo (ou ``None`` = tema padrão). O frontend deriva a
    # paleta completa de variáveis CSS a partir daqui.
    brand_theme: BrandTheme | None = None


class BrandThemeRequest(BrandTheme):
    """Define/atualiza o tema de marca da conta (modos claro e escuro)."""
