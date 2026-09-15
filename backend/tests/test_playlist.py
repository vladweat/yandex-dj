from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.api.deps import get_current_session, get_playlist_service
from app.core.security import encrypt_token
from app.db.models.session import Session
from app.db.models.user import User
from app.main import app
from app.schemas.llm import MusicProfile
from app.schemas.scoring import ScoredTrack
from app.schemas.track import TrackCandidate
from app.services.playlist_service import PlaylistService, build_playlist_description
from httpx import ASGITransport, AsyncClient

SAMPLE_PROFILE = MusicProfile(
    playlist_title="Ночной неон",
    playlist_description="Синтвейв для ночной поездки",
    primary_genres=["synthwave", "retrowave"],
    mood_tags=["nocturnal", "atmospheric"],
    vocal_type="any",
    reference_artists=["Kavinsky", "Perturbator", "Gunship", "Timecop1983"],
    search_queries=["synthwave night drive", "retrowave neon", "dark synth instrumental"],
    target_track_count=25,
)

SAMPLE_RANKED = [
    ScoredTrack(
        id="9442712",
        title="Nightcall",
        artists=["Kavinsky"],
        album="OutRun",
        genre="synthwave",
        duration_ms=259000,
        score=0.924,
    )
]


def test_build_playlist_description_appends_prompt() -> None:
    result = build_playlist_description(SAMPLE_PROFILE, "dark synthwave for night coding")
    assert "Синтвейв для ночной поездки" in result
    assert "Промпт: dark synthwave for night coding" in result


def test_build_playlist_description_skips_duplicate_prompt() -> None:
    prompt = "Синтвейв для ночной поездки"
    result = build_playlist_description(SAMPLE_PROFILE, prompt)
    assert result == SAMPLE_PROFILE.playlist_description


@pytest.mark.asyncio
async def test_playlist_service_generate_pipeline() -> None:
    llm = AsyncMock()
    llm.parse_prompt.return_value = SAMPLE_PROFILE

    retrieval = AsyncMock()
    retrieval.collect_candidates.return_value = [
        TrackCandidate(id="9442712", title="Nightcall", artists=["Kavinsky"])
    ]

    candidate = TrackCandidate(id="9442712", title="Nightcall", artists=["Kavinsky"])
    scoring = AsyncMock()
    scoring.rank_pool = AsyncMock(return_value=([(candidate, 0.924)], "embedding"))
    scoring.select = MagicMock(return_value=SAMPLE_RANKED)

    yandex = AsyncMock()
    mock_client = MagicMock()
    yandex.init_client.return_value = mock_client
    yandex.export_playlist.return_value = "https://music.yandex.ru/users/testuser/playlists/1003"

    service = PlaylistService(llm=llm, retrieval=retrieval, scoring=scoring, yandex=yandex)
    result = await service.generate(
        "dark synthwave for night coding",
        25,
        False,
        "oauth-token",
        "testuser",
    )

    llm.parse_prompt.assert_awaited_once()
    retrieval.collect_candidates.assert_awaited_once()
    scoring.rank_pool.assert_awaited()
    scoring.select.assert_called()
    yandex.export_playlist.assert_awaited_once_with(
        mock_client,
        title=SAMPLE_PROFILE.playlist_title,
        description=build_playlist_description(SAMPLE_PROFILE, "dark synthwave for night coding"),
        track_ids=["9442712"],
        login="testuser",
    )

    assert result.title == SAMPLE_PROFILE.playlist_title
    assert result.playlist_url.endswith("/playlists/1003")
    assert len(result.tracks) == 1
    assert result.tracks[0].artist == "Kavinsky"
    assert result.tracks[0].similarity_score == 0.924
    assert result.pool_stats is not None
    assert result.pool_stats.raw == 1
    assert result.pool_stats.selected == 1


@pytest.mark.asyncio
async def test_generate_playlist_endpoint() -> None:
    user = User(id=uuid4(), yandex_uid=42, login="testuser")
    session = Session(
        id=uuid4(),
        user_id=user.id,
        encrypted_token=encrypt_token("oauth-token"),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.user = user

    mock_service = AsyncMock()
    mock_service.generate.return_value = MagicMock(
        title=SAMPLE_PROFILE.playlist_title,
        description=SAMPLE_PROFILE.playlist_description,
        playlist_url="https://music.yandex.ru/users/testuser/playlists/1003",
        tracks=[
            MagicMock(
                id="9442712",
                title="Nightcall",
                artist="Kavinsky",
                duration_ms=259000,
                similarity_score=0.924,
            )
        ],
        model_dump=lambda: {
            "title": SAMPLE_PROFILE.playlist_title,
            "description": SAMPLE_PROFILE.playlist_description,
            "playlist_url": "https://music.yandex.ru/users/testuser/playlists/1003",
            "tracks": [
                {
                    "id": "9442712",
                    "title": "Nightcall",
                    "artist": "Kavinsky",
                    "duration_ms": 259000,
                    "similarity_score": 0.924,
                }
            ],
        },
    )

    app.dependency_overrides[get_current_session] = lambda: session
    app.dependency_overrides[get_playlist_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("app.api.v1.endpoints.playlists.decrypt_token", return_value="oauth-token"):
            response = await client.post(
                "/api/v1/playlists/generate",
                headers={"Authorization": f"Bearer {session.id}"},
                json={"prompt": "dark synthwave for night coding", "track_count": 25},
            )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == SAMPLE_PROFILE.playlist_title
    assert data["playlist_url"].endswith("/playlists/1003")
    assert data["tracks"][0]["artist"] == "Kavinsky"
    mock_service.generate.assert_awaited_once_with(
        "dark synthwave for night coding",
        25,
        False,
        "oauth-token",
        "testuser",
    )


@pytest.mark.asyncio
async def test_generate_playlist_unauthorized() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/playlists/generate",
            json={"prompt": "test"},
        )

    assert response.status_code == 401
