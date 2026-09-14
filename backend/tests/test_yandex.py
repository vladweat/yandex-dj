from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from app.api.deps import get_current_session, get_yandex_account_service
from app.db.models.session import Session
from app.db.models.user import User
from app.main import app
from app.schemas.yandex import YandexAccountSummary, YandexStatusResponse
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_yandex_account_returns_status() -> None:
    user = User(id=uuid4(), yandex_uid=42, login="testuser")
    session = Session(
        id=uuid4(),
        user_id=user.id,
        encrypted_token="encrypted",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.user = user

    mock_service = AsyncMock()
    mock_service.get_account_status.return_value = YandexStatusResponse(
        account=YandexAccountSummary(
            uid=42,
            login="testuser",
            display_name="Test User",
            service_available=True,
            region=225,
        ),
        default_email="test@yandex.ru",
        status={
            "account": {"uid": 42, "login": "testuser", "service_available": True},
            "default_email": "test@yandex.ru",
        },
    )

    app.dependency_overrides[get_current_session] = lambda: session
    app.dependency_overrides[get_yandex_account_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/yandex/account",
            headers={"Authorization": f"Bearer {session.id}"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["account"]["login"] == "testuser"
    assert data["default_email"] == "test@yandex.ru"
    assert data["status"]["account"]["uid"] == 42
    mock_service.get_account_status.assert_awaited_once_with(session)


@pytest.mark.asyncio
async def test_yandex_account_unauthorized() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/yandex/account")

    assert response.status_code == 401
