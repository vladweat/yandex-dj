from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.api.deps import get_auth_service, get_current_session
from app.core.security import decrypt_token
from app.db.models.session import Session
from app.db.models.user import User
from app.main import app
from app.schemas.auth import DeviceFlowPollResponse, DeviceFlowStartResponse
from app.services.auth_service import AuthService
from app.services.yandex_music_service import YandexMusicService
from httpx import ASGITransport, AsyncClient
from yandex_music import Account, DeviceCode, OAuthToken, Status


def _device_code() -> DeviceCode:
    return DeviceCode(
        device_code="device-123",
        user_code="ABCD-EFGH",
        verification_url="https://passport.yandex.ru/auth/device",
        expires_in=300,
        interval=5,
        client=None,
    )


def _account_status() -> Status:
    return Status(
        account=Account(
            now="2026-01-01T00:00:00",
            service_available=True,
            uid=42,
            login="testuser",
        ),
        permissions=None,
        client=None,
    )


@pytest.fixture
def mock_auth_service() -> AsyncMock:
    return AsyncMock(spec=AuthService)


@pytest.mark.asyncio
async def test_device_flow_start(mock_auth_service: AsyncMock) -> None:
    mock_auth_service.start_device_flow.return_value = DeviceFlowStartResponse(
        device_code="device-123",
        user_code="ABCD-EFGH",
        verification_url="https://passport.yandex.ru/auth/device",
        expires_in=300,
        interval=5,
    )
    app.dependency_overrides[get_auth_service] = lambda: mock_auth_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/device-flow/start")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["device_code"] == "device-123"
    assert data["user_code"] == "ABCD-EFGH"


@pytest.mark.asyncio
async def test_device_flow_poll_pending(mock_auth_service: AsyncMock) -> None:
    mock_auth_service.poll_device_flow.return_value = DeviceFlowPollResponse(status="pending")
    app.dependency_overrides[get_auth_service] = lambda: mock_auth_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/device-flow/poll",
            json={"device_code": "device-123"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_device_flow_poll_authenticated(mock_auth_service: AsyncMock) -> None:
    session_id = str(uuid4())
    mock_auth_service.poll_device_flow.return_value = DeviceFlowPollResponse(
        status="authenticated",
        session_id=session_id,
    )
    app.dependency_overrides[get_auth_service] = lambda: mock_auth_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/device-flow/poll",
            json={"device_code": "device-123"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "authenticated"
    assert data["session_id"] == session_id


@pytest.mark.asyncio
async def test_auth_service_poll_creates_session() -> None:
    db = AsyncMock()
    yandex = AsyncMock()
    user_repo = AsyncMock()
    session_repo = AsyncMock()

    user = User(id=uuid4(), yandex_uid=42, login="testuser")
    session = Session(
        id=uuid4(),
        user_id=user.id,
        encrypted_token="encrypted",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    yandex.poll_device_token.return_value = OAuthToken(access_token="ya-token", client=None)
    yandex.resolve_account.return_value = (42, "testuser")
    user_repo.upsert.return_value = user
    session_repo.create.return_value = session

    service = AuthService(db, yandex, user_repo, session_repo)
    result = await service.poll_device_flow("device-123")

    assert result.status == "authenticated"
    assert result.session_id == str(session.id)
    user_repo.upsert.assert_awaited_once_with(yandex_uid=42, login="testuser")
    session_repo.create.assert_awaited_once()
    encrypted = session_repo.create.await_args.kwargs["encrypted_token"]
    assert decrypt_token(encrypted) == "ya-token"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_session_from_token_skips_yandex_with_profile() -> None:
    db = AsyncMock()
    yandex = AsyncMock()
    user_repo = AsyncMock()
    session_repo = AsyncMock()

    user = User(id=uuid4(), yandex_uid=42, login="testuser")
    session = Session(
        id=uuid4(),
        user_id=user.id,
        encrypted_token="encrypted",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    user_repo.upsert.return_value = user
    session_repo.create.return_value = session

    service = AuthService(db, yandex, user_repo, session_repo)
    result = await service.create_session_from_token(
        "ya-token",
        yandex_uid=42,
        login="testuser",
    )

    assert result.status == "authenticated"
    yandex.resolve_account.assert_not_called()
    user_repo.upsert.assert_awaited_once_with(yandex_uid=42, login="testuser")
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_yandex_music_service_resolve_account() -> None:
    service = YandexMusicService()
    mock_client = AsyncMock()
    service.init_client = AsyncMock(return_value=mock_client)
    service.get_account_status = AsyncMock(return_value=_account_status())

    uid, login = await service.resolve_account("ya-token")

    assert uid == 42
    assert login == "testuser"
    service.init_client.assert_awaited_once_with("ya-token")
    service.get_account_status.assert_awaited_once_with(mock_client)


@pytest.mark.asyncio
async def test_auth_me_returns_profile() -> None:
    user = User(id=uuid4(), yandex_uid=42, login="testuser")
    session = Session(
        id=uuid4(),
        user_id=user.id,
        encrypted_token="encrypted",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.user = user
    app.dependency_overrides[get_current_session] = lambda: session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {session.id}"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["login"] == "testuser"
    assert data["yandex_uid"] == 42
    assert data["session_id"] == str(session.id)


@pytest.mark.asyncio
async def test_auth_me_unauthorized_without_header() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_yandex_music_service_request_device_code() -> None:
    service = YandexMusicService()
    expected = _device_code()

    mock_client = AsyncMock()
    mock_client.request_device_code.return_value = expected
    service._create_client = MagicMock(return_value=mock_client)

    result = await service.request_device_code()
    assert result.device_code == expected.device_code
