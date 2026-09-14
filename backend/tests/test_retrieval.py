from unittest.mock import AsyncMock, MagicMock

import pytest
from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate
from app.services.retrieval_service import RetrievalService
from app.utils.search_queries import expand_search_queries
from app.utils.tracks import normalize_pool
from yandex_music import Artist, Track


def _profile() -> MusicProfile:
    return MusicProfile(
        playlist_title="Night Drive",
        playlist_description="Dark synthwave for coding",
        primary_genres=["synthwave", "electronic"],
        mood_tags=["dark", "focus"],
        vocal_type="instrumental_only",
        reference_artists=[
            "Kavinsky",
            "Perturbator",
            "Carpenter Brut",
            "Gunship",
        ],
        search_queries=[
            "synthwave night drive",
            "dark synth instrumental",
            "retrowave coding",
        ],
        target_track_count=25,
    )


def _track(
    track_id: str,
    title: str,
    artist: str,
    *,
    available: bool = True,
) -> TrackCandidate:
    return TrackCandidate(
        id=track_id,
        title=title,
        artists=[artist],
        available=available,
    )


def test_normalize_pool_dedup_by_id() -> None:
    tracks = [
        _track("1", "Nightcall", "Kavinsky"),
        _track("1", "Nightcall", "Kavinsky"),
        _track("2", "Turbo Killer", "Carpenter Brut"),
    ]
    result = normalize_pool(tracks)
    assert len(result) == 2


def test_normalize_pool_dedup_by_artist_title() -> None:
    tracks = [
        _track("1", "Nightcall", "Kavinsky"),
        _track("99", "Nightcall", "Kavinsky"),
        _track("2", "Turbo Killer", "Carpenter Brut"),
    ]
    result = normalize_pool(tracks)
    assert len(result) == 2
    assert {t.id for t in result} == {"1", "2"}


def test_normalize_pool_filters_unavailable() -> None:
    tracks = [
        _track("1", "Nightcall", "Kavinsky", available=False),
        _track("2", "Turbo Killer", "Carpenter Brut"),
    ]
    result = normalize_pool(tracks)
    assert len(result) == 1
    assert result[0].id == "2"


def test_expand_search_queries_adds_genres_and_artists() -> None:
    used = {q.lower() for q in _profile().search_queries}
    extra = expand_search_queries(_profile(), used=used, pass_num=0)
    assert any("synthwave" in q for q in extra)
    assert any("Kavinsky" in q for q in extra)
    assert len(extra) <= 12


def _ym_track(track_id: str, title: str, artist_name: str) -> Track:
    return Track(
        id=track_id,
        title=title,
        available=True,
        artists=[Artist(id=1, name=artist_name)],
        albums=[],
    )


@pytest.mark.asyncio
async def test_collect_candidates_parallel_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.retrieval_service.settings.target_candidates_pool", 0)
    monkeypatch.setattr("app.services.retrieval_service.settings.retrieval_expand_passes", 0)

    profile = _profile()
    yandex = AsyncMock()
    cache = AsyncMock()
    cache.get_many.return_value = {}
    cache.set_many.return_value = None

    client = MagicMock()
    yandex.init_client.return_value = client
    yandex.search_tracks.side_effect = [
        [_ym_track("s1", "Search One", "Artist A")],
        [_ym_track("s2", "Search Two", "Artist B")],
        [_ym_track("s3", "Search Three", "Artist C")],
    ]
    yandex.search_artist_id.return_value = "artist-42"
    yandex.artists_top_tracks.return_value = [
        _ym_track("a1", "Artist Track", "Kavinsky"),
    ]
    yandex.fetch_tracks.return_value = []

    service = RetrievalService(yandex, cache)
    result = await service.collect_candidates(profile, "token-123")

    assert len(result) >= 4
    assert yandex.search_tracks.await_count == len(profile.search_queries)
    assert yandex.search_artist_id.await_count == len(profile.reference_artists)
    yandex.init_client.assert_awaited_once_with("token-123")


@pytest.mark.asyncio
async def test_collect_candidates_with_similar_tracks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.retrieval_service.settings.target_candidates_pool", 0)
    monkeypatch.setattr("app.services.retrieval_service.settings.retrieval_expand_passes", 0)

    profile = _profile()
    yandex = AsyncMock()
    cache = AsyncMock()
    cache.get_many.return_value = {}
    cache.set_many.return_value = None

    client = MagicMock()
    yandex.init_client.return_value = client
    yandex.search_tracks.return_value = []
    yandex.search_artist_id.return_value = None
    yandex.tracks_similar_list.return_value = [
        _ym_track("sim1", "Similar Track", "Artist X"),
    ]
    yandex.fetch_tracks.return_value = []

    service = RetrievalService(yandex, cache)
    result = await service.collect_candidates(
        profile,
        "token-123",
        reference_track_id="ref-track",
    )

    assert len(result) == 1
    assert result[0].id == "sim1"
    yandex.tracks_similar_list.assert_awaited_once_with(client, "ref-track")
