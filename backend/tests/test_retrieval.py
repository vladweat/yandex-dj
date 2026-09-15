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
    monkeypatch.setattr("app.services.retrieval_service.settings.min_clean_candidates", 0)

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
    yandex.tracks_similar_list.return_value = []

    service = RetrievalService(yandex, cache)
    result = await service.collect_candidates(profile, "token-123")

    assert len(result) >= 4
    assert yandex.search_tracks.await_count == len(profile.search_queries)
    assert yandex.search_artist_id.await_count >= len(profile.reference_artists)
    yandex.init_client.assert_awaited_once_with("token-123")


@pytest.mark.asyncio
async def test_collect_candidates_expands_anchor_similar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.retrieval_service.settings.target_candidates_pool", 0)
    monkeypatch.setattr("app.services.retrieval_service.settings.retrieval_expand_passes", 0)
    monkeypatch.setattr("app.services.retrieval_service.settings.min_clean_candidates", 0)

    profile = _profile()
    yandex = AsyncMock()
    cache = AsyncMock()
    cache.get_many.return_value = {}
    cache.set_many.return_value = None

    client = MagicMock()
    yandex.init_client.return_value = client
    yandex.search_tracks.return_value = []
    yandex.search_artist_id.return_value = "artist-42"
    yandex.artists_top_tracks.return_value = [
        _ym_track("a1", "Nightcall", "Kavinsky"),
    ]
    yandex.tracks_similar_list.return_value = [
        _ym_track("sim1", "Similar Track", "Artist X"),
    ]
    yandex.fetch_tracks.return_value = []

    service = RetrievalService(yandex, cache)
    result = await service.collect_candidates(profile, "token-123")

    assert any(track.id == "sim1" for track in result)
    yandex.tracks_similar_list.assert_awaited()


@pytest.mark.asyncio
async def test_expand_discovered_artists_fetches_top_tracks() -> None:
    profile = _profile()
    yandex = AsyncMock()
    cache = AsyncMock()
    service = RetrievalService(yandex, cache)
    client = MagicMock()

    candidates = [
        _track("s1", "Power", "Pompeya"),
        _track("a1", "Nightcall", "Kavinsky"),
    ]
    yandex.search_artist_id.return_value = "artist-pompeya"
    yandex.artists_top_tracks.return_value = [
        _ym_track("p1", "Passing By", "Pompeya"),
        _ym_track("p2", "90", "Pompeya"),
    ]
    yandex.tracks_similar_list.return_value = []

    expanded = await service._expand_discovered_artists(
        client,
        profile,
        candidates,
        seen_artists=set(),
        used_seed_ids=set(),
    )

    assert any(track.id == "p1" for track in expanded)
    yandex.search_artist_id.assert_awaited_with(client, "Pompeya")


def test_rank_discovered_artists_prefers_frequency() -> None:
    profile = _profile()
    candidates = [
        _track("1", "A", "Rare"),
        _track("2", "B", "Hot"),
        _track("3", "C", "Hot"),
        _track("4", "D", "Hot"),
        _track("5", "E", "Kavinsky"),
    ]
    ranked = RetrievalService._rank_discovered_artists(
        candidates,
        profile,
        seen_artists=set(),
        max_artists=2,
    )
    assert ranked[0] == "Hot"
    assert "Kavinsky" not in ranked


@pytest.mark.asyncio
async def test_expand_discovered_artists_pulls_similar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.retrieval_service.settings.discovered_similar_seeds", 2)
    profile = _profile()
    yandex = AsyncMock()
    cache = AsyncMock()
    service = RetrievalService(yandex, cache)
    client = MagicMock()

    candidates = [
        _track("s1", "Power", "Pompeya"),
        _track("s2", "90", "Pompeya"),
    ]
    yandex.search_artist_id.return_value = "artist-pompeya"
    yandex.artists_top_tracks.return_value = [
        _ym_track("p1", "Passing By", "Pompeya"),
    ]
    yandex.tracks_similar_list.return_value = [
        _ym_track("sim1", "Neighbor", "Soulive"),
    ]

    expanded = await service._expand_discovered_artists(
        client,
        profile,
        candidates,
        seen_artists=set(),
        used_seed_ids=set(),
    )

    assert any(track.id == "sim1" for track in expanded)
    yandex.tracks_similar_list.assert_awaited()


@pytest.mark.asyncio
async def test_collect_candidates_with_similar_tracks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.retrieval_service.settings.target_candidates_pool", 0)
    monkeypatch.setattr("app.services.retrieval_service.settings.retrieval_expand_passes", 0)
    monkeypatch.setattr("app.services.retrieval_service.settings.min_clean_candidates", 0)

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
    yandex.tracks_similar_list.assert_any_await(client, "ref-track")
