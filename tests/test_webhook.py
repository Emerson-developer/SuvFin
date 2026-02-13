"""
Testes para o endpoint de webhook.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.anyio
async def test_health_check(client: AsyncClient):
    """Testa o endpoint de health check."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "SuvFin"


@pytest.mark.anyio
async def test_webhook_verify_success(client: AsyncClient):
    """Testa a verificação do webhook com token correto."""
    from app.config.settings import settings

    response = await client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.challenge": "test_challenge_123",
            "hub.verify_token": settings.WEBHOOK_VERIFY_TOKEN,
        },
    )
    assert response.status_code == 200
    assert response.text == "test_challenge_123"


@pytest.mark.anyio
async def test_webhook_verify_fail(client: AsyncClient):
    """Testa a verificação com token errado."""
    response = await client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.challenge": "test_challenge_123",
            "hub.verify_token": "wrong_token",
        },
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_webhook_post_empty(client: AsyncClient):
    """Testa o POST com payload sem mensagem."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "5511999999999",
                                "phone_number_id": "123456",
                            },
                        },
                    }
                ],
            }
        ],
    }
    response = await client.post("/webhook", json=payload)
    assert response.status_code == 200


@pytest.mark.anyio
async def test_root(client: AsyncClient):
    """Testa a rota raiz."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "SuvFin" in response.json()["message"]
