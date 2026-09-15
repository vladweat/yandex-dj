import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.api.deps import get_current_session, get_playlist_service
from app.core.exceptions import NotFoundError
from app.core.security import encrypt_token
from app.db.models.session import Session
from app.db.models.user import User
from app.main import app
from app.schemas.llm import MusicProfile
from app.schemas.playlist import (
    PlaylistGenerateResponse,
    PlaylistGenerationOptions,
    PlaylistHistoryItem,
    PlaylistHistoryResponse,
    PlaylistPoolStats,
    PlaylistTrackResponse,
)
from app.schemas.scoring import ScoredTrack
from app.schemas.track import TrackCandidate
from app.services.playlist_service import (
    PlaylistService,
    apply_exclude_artists,
    build_playlist_description,
    filter_excluded_candidates,
    yandex_kind_from_url,
)
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

USER_ID = uuid4()
GENERATION_ID = uuid4()


def _sample_response() -> PlaylistGenerateResponse:
    return PlaylistGenerateResponse(
        id=GENERATION_ID,
        prompt="dark synthwave for night coding",
        title=SAMPLE_PROFILE.playlist_title,
        description=SAMPLE_PROFILE.playlist_description,
        playlist_url="https://music.yandex.ru/users/testuser/playlists/1003",
        tracks=[
            PlaylistTrackResponse(
                id="9442712",
                title="Nightcall",
                artist="Kavinsky",
                duration_ms=259000,
                similarity_score=0.924,
            )
        ],
        pool_stats=PlaylistPoolStats(raw=1, clean=1, selected=1),
        profile=SAMPLE_PROFILE,
        options=PlaylistGenerationOptions(
            track_count=25,
            instrumental_only=False,
            exclude_artists=[],
            diversity="normal",
        ),
        warnings=[],
    )


def test_build_playlist_description_appends_prompt() -> None:
    result = build_playlist_description(SAMPLE_PROFILE, "dark synthwave for night coding")
    assert "Синтвейв для ночной поездки" in result
    assert "Промпт: dark synthwave for night coding" in result


def test_build_playlist_description_skips_duplicate_prompt() -> None:
    prompt = "Синтвейв для ночной поездки"
    result = build_playlist_description(SAMPLE_PROFILE, prompt)
    assert result == SAMPLE_PROFILE.playlist_description


def test_yandex_kind_from_url() -> None:
    assert yandex_kind_from_url("https://music.yandex.ru/users/u/playlists/1003") == "1003"
    assert yandex_kind_from_url("https://example.com") is None


def test_apply_exclude_artists_removes_when_enough_remain() -> None:
    profile = SAMPLE_PROFILE.model_copy(
        update={
            "reference_artists": [
                "Kavinsky",
                "Perturbator",
                "Gunship",
                "Timecop1983",
                "Carpenter Brut",
            ]
        }
    )
    updated, warnings = apply_exclude_artists(profile, ["Kavinsky"])
    assert "Kavinsky" not in updated.reference_artists
    assert len(updated.reference_artists) == 4
    assert warnings == []


def test_apply_exclude_artists_keeps_anchors_if_below_four() -> None:
    updated, warnings = apply_exclude_artists(SAMPLE_PROFILE, ["Kavinsky"])
    assert updated.reference_artists == SAMPLE_PROFILE.reference_artists
    assert len(warnings) == 1
    assert "exclude_artists не сняты с якорей" in warnings[0]
    assert "Kavinsky" in warnings[0]


def test_filter_excluded_candidates() -> None:
    candidates = [
        TrackCandidate(id="1", title="A", artists=["Kavinsky"]),
        TrackCandidate(id="2", title="B", artists=["Gunship"]),
    ]
    kept = filter_excluded_candidates(candidates, ["Kavinsky"])
    assert [track.id for track in kept] == ["2"]


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

    repo = AsyncMock()
    saved = MagicMock()
    saved.id = GENERATION_ID
    repo.create.return_value = saved

    service = PlaylistService(
        llm=llm, retrieval=retrieval, scoring=scoring, yandex=yandex, repo=repo
    )
    result = await service.generate(
        prompt="dark synthwave for night coding",
        track_count=25,
        instrumental_only=False,
        access_token="oauth-token",
        login="testuser",
        user_id=USER_ID,
        diversity="high",
    )

    llm.parse_prompt.assert_awaited_once()
    retrieval.collect_candidates.assert_awaited_once()
    scoring.rank_pool.assert_awaited()
    scoring.select.assert_called()
    assert scoring.select.call_args.kwargs.get("diversity") == "high"
    yandex.export_playlist.assert_awaited_once_with(
        mock_client,
        title=SAMPLE_PROFILE.playlist_title,
        description=build_playlist_description(SAMPLE_PROFILE, "dark synthwave for night coding"),
        track_ids=["9442712"],
        login="testuser",
    )
    repo.create.assert_awaited_once()

    assert result.id == GENERATION_ID
    assert result.prompt == "dark synthwave for night coding"
    assert result.profile.playlist_title == SAMPLE_PROFILE.playlist_title
    assert result.title == SAMPLE_PROFILE.playlist_title
    assert result.playlist_url.endswith("/playlists/1003")
    assert len(result.tracks) == 1
    assert result.tracks[0].artist == "Kavinsky"
    assert result.tracks[0].similarity_score == 0.924
    assert result.pool_stats is not None
    assert result.pool_stats.raw == 1
    assert result.pool_stats.selected == 1
    assert result.options is not None
    assert result.options.diversity == "high"
    assert result.warnings == []


@pytest.mark.asyncio
async def test_playlist_service_feedback_uses_rank_pool_merge() -> None:
    llm = AsyncMock()
    short_profile = SAMPLE_PROFILE.model_copy(update={"target_track_count": 2})
    llm.parse_prompt.return_value = short_profile

    first = TrackCandidate(id="1", title="A", artists=["Other Band"])
    second = TrackCandidate(id="2", title="B", artists=["New Band"])
    retrieval = AsyncMock()
    retrieval.collect_candidates.return_value = [first]
    retrieval.expand_from_artists = AsyncMock(return_value=[first, second])

    scoring = AsyncMock()
    scoring.rank_pool = AsyncMock(return_value=([(first, 0.9)], "embedding"))
    scoring.rank_pool_merge = AsyncMock(return_value=([(second, 0.95), (first, 0.9)], "embedding"))
    scoring.select = MagicMock(
        side_effect=[
            [ScoredTrack.from_candidate(first, 0.9)],
            [
                ScoredTrack.from_candidate(second, 0.95),
                ScoredTrack.from_candidate(first, 0.9),
            ],
        ]
    )

    yandex = AsyncMock()
    yandex.init_client.return_value = MagicMock()
    yandex.export_playlist.return_value = "https://music.yandex.ru/users/testuser/playlists/1005"

    repo = AsyncMock()
    saved = MagicMock()
    saved.id = GENERATION_ID
    repo.create.return_value = saved

    service = PlaylistService(
        llm=llm, retrieval=retrieval, scoring=scoring, yandex=yandex, repo=repo
    )
    with patch(
        "app.services.playlist_service.non_anchor_artists_from_ranked",
        return_value=["New Band"],
    ):
        result = await service.generate(
            prompt="test",
            track_count=2,
            instrumental_only=False,
            access_token="oauth-token",
            login="testuser",
            user_id=USER_ID,
        )

    scoring.rank_pool.assert_awaited_once()
    scoring.rank_pool_merge.assert_awaited_once()
    assert result.pool_stats is not None
    assert result.pool_stats.selected == 2


@pytest.mark.asyncio
async def test_playlist_service_source_id_skips_llm() -> None:
    llm = AsyncMock()
    retrieval = AsyncMock()
    retrieval.collect_candidates.return_value = [
        TrackCandidate(id="9442712", title="Nightcall", artists=["Kavinsky"])
    ]
    candidate = TrackCandidate(id="9442712", title="Nightcall", artists=["Kavinsky"])
    scoring = AsyncMock()
    scoring.rank_pool = AsyncMock(return_value=([(candidate, 0.924)], "embedding"))
    scoring.select = MagicMock(return_value=SAMPLE_RANKED)
    yandex = AsyncMock()
    yandex.init_client.return_value = MagicMock()
    yandex.export_playlist.return_value = "https://music.yandex.ru/users/testuser/playlists/1004"

    source_id = uuid4()
    source = MagicMock()
    source.profile = SAMPLE_PROFILE.model_dump()

    repo = AsyncMock()
    repo.get_by_id_for_user.return_value = source
    saved = MagicMock()
    saved.id = GENERATION_ID
    repo.create.return_value = saved

    service = PlaylistService(
        llm=llm, retrieval=retrieval, scoring=scoring, yandex=yandex, repo=repo
    )
    result = await service.generate(
        prompt="dark synthwave for night coding",
        track_count=25,
        instrumental_only=False,
        access_token="oauth-token",
        login="testuser",
        user_id=USER_ID,
        source_id=source_id,
    )

    llm.parse_prompt.assert_not_awaited()
    repo.get_by_id_for_user.assert_awaited_once_with(source_id, USER_ID)
    assert result.id == GENERATION_ID


@pytest.mark.asyncio
async def test_playlist_service_source_id_not_found() -> None:
    repo = AsyncMock()
    repo.get_by_id_for_user.return_value = None
    service = PlaylistService(
        llm=AsyncMock(),
        retrieval=AsyncMock(),
        scoring=AsyncMock(),
        yandex=AsyncMock(),
        repo=repo,
    )
    with pytest.raises(NotFoundError):
        await service.generate(
            prompt="x",
            track_count=25,
            instrumental_only=False,
            access_token="t",
            login="u",
            user_id=USER_ID,
            source_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_generate_playlist_endpoint() -> None:
    user = User(id=USER_ID, yandex_uid=42, login="testuser")
    session = Session(
        id=uuid4(),
        user_id=user.id,
        encrypted_token=encrypt_token("oauth-token"),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.user = user

    mock_service = AsyncMock()
    mock_service.generate.return_value = _sample_response()

    app.dependency_overrides[get_current_session] = lambda: session
    app.dependency_overrides[get_playlist_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("app.api.v1.endpoints.playlists.decrypt_token", return_value="oauth-token"):
            response = await client.post(
                "/api/v1/playlists/generate",
                headers={"Authorization": f"Bearer {session.id}"},
                json={
                    "prompt": "dark synthwave for night coding",
                    "track_count": 25,
                    "diversity": "high",
                    "exclude_artists": ["Kavinsky"],
                },
            )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(GENERATION_ID)
    assert data["prompt"] == "dark synthwave for night coding"
    assert data["profile"]["playlist_title"] == SAMPLE_PROFILE.playlist_title
    assert data["title"] == SAMPLE_PROFILE.playlist_title
    assert data["playlist_url"].endswith("/playlists/1003")
    assert data["tracks"][0]["artist"] == "Kavinsky"
    mock_service.generate.assert_awaited_once()
    call_kwargs = mock_service.generate.await_args.kwargs
    assert call_kwargs["prompt"] == "dark synthwave for night coding"
    assert call_kwargs["track_count"] == 25
    assert call_kwargs["instrumental_only"] is False
    assert call_kwargs["diversity"] == "high"
    assert call_kwargs["exclude_artists"] == ["Kavinsky"]
    assert call_kwargs["user_id"] == USER_ID


@pytest.mark.asyncio
async def test_list_and_get_playlist_endpoints() -> None:
    user = User(id=USER_ID, yandex_uid=42, login="testuser")
    session = Session(
        id=uuid4(),
        user_id=user.id,
        encrypted_token=encrypt_token("oauth-token"),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.user = user

    mock_service = AsyncMock()
    mock_service.list_history.return_value = PlaylistHistoryResponse(
        items=[
            PlaylistHistoryItem(
                id=GENERATION_ID,
                prompt="dark synthwave",
                title="Ночной неон",
                playlist_url="https://music.yandex.ru/users/testuser/playlists/1003",
                pool_stats=PlaylistPoolStats(raw=10, clean=8, selected=5),
                options=PlaylistGenerationOptions(
                    track_count=25,
                    instrumental_only=True,
                    exclude_artists=["Kavinsky"],
                    diversity="high",
                ),
                created_at=datetime.now(UTC),
            )
        ],
        limit=20,
        offset=0,
    )
    mock_service.get_generation.return_value = _sample_response()

    app.dependency_overrides[get_current_session] = lambda: session
    app.dependency_overrides[get_playlist_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        list_response = await client.get(
            "/api/v1/playlists",
            headers={"Authorization": f"Bearer {session.id}"},
        )
        get_response = await client.get(
            f"/api/v1/playlists/{GENERATION_ID}",
            headers={"Authorization": f"Bearer {session.id}"},
        )

    app.dependency_overrides.clear()

    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["id"] == str(GENERATION_ID)
    assert list_response.json()["items"][0]["options"]["diversity"] == "high"
    assert get_response.status_code == 200
    assert get_response.json()["profile"]["reference_artists"][0] == "Kavinsky"


@pytest.mark.asyncio
async def test_generate_playlist_timeout() -> None:
    user = User(id=USER_ID, yandex_uid=42, login="testuser")
    session = Session(
        id=uuid4(),
        user_id=user.id,
        encrypted_token=encrypt_token("oauth-token"),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.user = user

    async def slow_generate(**kwargs):
        await asyncio.sleep(1.0)
        return _sample_response()

    mock_service = AsyncMock()
    mock_service.generate = slow_generate

    app.dependency_overrides[get_current_session] = lambda: session
    app.dependency_overrides[get_playlist_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with (
            patch("app.api.v1.endpoints.playlists.decrypt_token", return_value="oauth-token"),
            patch("app.api.v1.endpoints.playlists.settings") as mock_settings,
        ):
            mock_settings.pipeline_timeout_sec = 0.05
            response = await client.post(
                "/api/v1/playlists/generate",
                headers={"Authorization": f"Bearer {session.id}"},
                json={"prompt": "dark synthwave for night coding"},
            )

    app.dependency_overrides.clear()

    assert response.status_code == 504
    assert "PIPELINE_TIMEOUT_SEC" in response.json()["detail"]


@pytest.mark.asyncio
async def test_generate_playlist_unauthorized() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/playlists/generate",
            json={"prompt": "test"},
        )

    assert response.status_code == 401
