import pytest
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_cors_preflight_device_flow_start() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options(
            "/api/v1/auth/device-flow/start",
            headers={
                "Origin": "http://localhost:3001",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-requested-with",
            },
        )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3001"
