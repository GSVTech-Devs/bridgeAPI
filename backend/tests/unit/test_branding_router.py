# Testes das rotas /portal/branding (logo da conta) e da validação de upload.
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.domains.branding.service import (
    InvalidBrandColorError,
    InvalidLogoError,
    normalize_brand_theme,
    validate_brand_color,
    validate_logo,
)

# Cabeçalhos PNG/JPEG/WEBP válidos (magic bytes).
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 32
WEBP_BYTES = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 32


def _token(role: str, account_id: uuid.UUID | None = None) -> str:
    claims = {"user_id": str(uuid.uuid4())}
    if account_id is not None:
        claims["account_id"] = str(account_id)
    return create_access_token("user@acme.com", role=role, extra_claims=claims)


def _headers(role: str, account_id: uuid.UUID | None = None) -> dict:
    return {"Authorization": f"Bearer {_token(role, account_id or uuid.uuid4())}"}


def _account(**kwargs) -> SimpleNamespace:
    base = dict(
        id=uuid.uuid4(),
        logo_data=None,
        logo_content_type=None,
        brand_theme=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


# ---------------------------------------------------------------------------
# validate_logo (unidade pura)
# ---------------------------------------------------------------------------
def test_validate_logo_accepts_png():
    assert validate_logo("image/png", PNG_BYTES) == "image/png"


def test_validate_logo_normalizes_content_type():
    assert validate_logo("image/png; charset=binary", PNG_BYTES) == "image/png"


def test_validate_logo_accepts_webp():
    assert validate_logo("image/webp", WEBP_BYTES) == "image/webp"


def test_validate_logo_rejects_unknown_type():
    with pytest.raises(InvalidLogoError):
        validate_logo("image/gif", PNG_BYTES)


def test_validate_logo_rejects_content_type_mismatch():
    # Diz que é PNG mas o conteúdo é JPEG → rejeitado.
    with pytest.raises(InvalidLogoError):
        validate_logo("image/png", JPEG_BYTES)


def test_validate_logo_rejects_too_large():
    with pytest.raises(InvalidLogoError):
        validate_logo("image/png", PNG_BYTES[:8] + b"\x00" * (5 * 1024 * 1024 + 1))


def test_validate_logo_rejects_empty():
    with pytest.raises(InvalidLogoError):
        validate_logo("image/png", b"")


# ---------------------------------------------------------------------------
# Autorização das rotas
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_cannot_read_branding(client: AsyncClient) -> None:
    resp = await client.get("/portal/branding", headers=_headers("admin"))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_member_cannot_upload_logo(client: AsyncClient) -> None:
    resp = await client.put(
        "/portal/branding/logo",
        files={"file": ("logo.png", PNG_BYTES, "image/png")},
        headers=_headers("member"),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_member_can_read_branding(client: AsyncClient) -> None:
    with patch(
        "app.domains.branding.router.get_account_by_id",
        new=AsyncMock(return_value=_account()),
    ):
        resp = await client.get("/portal/branding", headers=_headers("member"))
    assert resp.status_code == 200
    assert resp.json() == {"logo_data_uri": None, "brand_theme": None}


@pytest.mark.asyncio
async def test_owner_uploads_valid_logo(client: AsyncClient) -> None:
    stored = _account(logo_data=PNG_BYTES, logo_content_type="image/png")
    with patch(
        "app.domains.branding.router.set_account_logo",
        new=AsyncMock(return_value=stored),
    ):
        resp = await client.put(
            "/portal/branding/logo",
            files={"file": ("logo.png", PNG_BYTES, "image/png")},
            headers=_headers("owner"),
        )
    assert resp.status_code == 200
    assert resp.json()["logo_data_uri"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_owner_upload_rejects_bad_content(client: AsyncClient) -> None:
    # Content-Type diz PNG, mas os bytes não são de imagem → 422.
    resp = await client.put(
        "/portal/branding/logo",
        files={"file": ("fake.png", b"not an image", "image/png")},
        headers=_headers("owner"),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_owner_can_delete_logo(client: AsyncClient) -> None:
    with patch(
        "app.domains.branding.router.clear_account_logo",
        new=AsyncMock(return_value=_account()),
    ):
        resp = await client.delete(
            "/portal/branding/logo", headers=_headers("owner")
        )
    assert resp.status_code == 200
    assert resp.json() == {"logo_data_uri": None, "brand_theme": None}


# ---------------------------------------------------------------------------
# validate_brand_color (unidade pura)
# ---------------------------------------------------------------------------
def test_validate_brand_color_accepts_hex():
    assert validate_brand_color("#2B5AB5") == "#2b5ab5"


def test_validate_brand_color_strips_and_lowercases():
    assert validate_brand_color("  #ABCDEF ") == "#abcdef"


def test_validate_brand_color_rejects_without_hash():
    with pytest.raises(InvalidBrandColorError):
        validate_brand_color("2b5ab5")


def test_validate_brand_color_rejects_short():
    with pytest.raises(InvalidBrandColorError):
        validate_brand_color("#fff")


def test_validate_brand_color_rejects_non_hex():
    with pytest.raises(InvalidBrandColorError):
        validate_brand_color("#zzzzzz")


# ---------------------------------------------------------------------------
# normalize_brand_theme (unidade pura)
# ---------------------------------------------------------------------------
def test_normalize_brand_theme_lowercases_and_drops_empty():
    result = normalize_brand_theme(
        {"light": {"primary": "#2B5AB5", "secondary": None}, "dark": {}}
    )
    assert result == {"light": {"primary": "#2b5ab5"}, "dark": {}}


def test_normalize_brand_theme_keeps_background():
    result = normalize_brand_theme({"light": {"background": "#FFFFFF"}})
    assert result["light"] == {"background": "#ffffff"}
    assert result["dark"] == {}


# ---------------------------------------------------------------------------
# Rotas de tema de marca
# ---------------------------------------------------------------------------
_THEME = {
    "light": {"primary": "#2b5ab5", "background": "#f3faff"},
    "dark": {"primary": "#adc6ff", "background": "#00161f"},
}


@pytest.mark.asyncio
async def test_member_cannot_update_colors(client: AsyncClient) -> None:
    resp = await client.put(
        "/portal/branding/colors",
        json=_THEME,
        headers=_headers("member"),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_owner_updates_theme(client: AsyncClient) -> None:
    stored = _account(
        brand_theme={
            "light": {"primary": "#2b5ab5", "background": "#f3faff"},
            "dark": {"primary": "#adc6ff", "background": "#00161f"},
        }
    )
    with patch(
        "app.domains.branding.router.set_account_brand_theme",
        new=AsyncMock(return_value=stored),
    ):
        resp = await client.put(
            "/portal/branding/colors",
            json=_THEME,
            headers=_headers("owner"),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["brand_theme"]["light"]["primary"] == "#2b5ab5"
    assert body["brand_theme"]["dark"]["background"] == "#00161f"


@pytest.mark.asyncio
async def test_owner_update_theme_accepts_partial(client: AsyncClient) -> None:
    # Só uma cor de um modo — os demais slots ficam no padrão (None).
    stored = _account(brand_theme={"light": {"primary": "#dc2626"}, "dark": {}})
    with patch(
        "app.domains.branding.router.set_account_brand_theme",
        new=AsyncMock(return_value=stored),
    ):
        resp = await client.put(
            "/portal/branding/colors",
            json={"light": {"primary": "#dc2626"}},
            headers=_headers("owner"),
        )
    assert resp.status_code == 200
    assert resp.json()["brand_theme"]["light"]["primary"] == "#dc2626"
    assert resp.json()["brand_theme"]["light"]["secondary"] is None


@pytest.mark.asyncio
async def test_owner_update_theme_rejects_invalid_hex(client: AsyncClient) -> None:
    # Falha já na validação do schema (Pydantic) → 422, sem tocar no banco.
    resp = await client.put(
        "/portal/branding/colors",
        json={"light": {"primary": "blue"}, "dark": {}},
        headers=_headers("owner"),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_owner_can_reset_theme(client: AsyncClient) -> None:
    with patch(
        "app.domains.branding.router.clear_account_brand_theme",
        new=AsyncMock(return_value=_account()),
    ):
        resp = await client.delete(
            "/portal/branding/colors", headers=_headers("owner")
        )
    assert resp.status_code == 200
    assert resp.json() == {"logo_data_uri": None, "brand_theme": None}
