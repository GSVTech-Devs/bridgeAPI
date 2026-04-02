# RED → GREEN
# Este teste foi escrito antes do endpoint existir (ciclo TDD).
# O endpoint GET /health deve retornar {"status": "ok"} com HTTP 200.
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_response_has_correct_content_type(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert "application/json" in response.headers["content-type"]
