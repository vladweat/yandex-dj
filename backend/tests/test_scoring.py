from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate
from app.services.scoring_service import ScoringService
from app.utils.scoring import (
    apply_diversity_filter,
    apply_reference_artist_boost,
    build_prompt_text,
    cosine_scores,
    fallback_scores,
    max_tracks_per_artist,
    merge_embedding_rank,
    select_embedding_pool,
)


def _profile(*, target_track_count: int = 25) -> MusicProfile:
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
        target_track_count=target_track_count,
    )


def _track(track_id: str, title: str, artist: str, *, genre: str = "") -> TrackCandidate:
    return TrackCandidate(
        id=track_id,
        title=title,
        artists=[artist],
        genre=genre,
    )


def test_max_tracks_per_artist() -> None:
    assert max_tracks_per_artist(25) == 2
    assert max_tracks_per_artist(26) == 3
    assert max_tracks_per_artist(50) == 3


def test_build_prompt_text_includes_profile_fields() -> None:
    text = build_prompt_text(_profile(), user_prompt="night coding")
    assert "night coding" in text
    assert "Dark synthwave for coding" in text
    assert "synthwave" in text
    assert "Kavinsky" in text
    assert "instrumental_only" in text


def test_cosine_scores_identical_vectors() -> None:
    vec = np.array([1.0, 0.0, 0.0])
    docs = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    scores = cosine_scores(vec, docs)
    assert scores[0] == pytest.approx(1.0)
    assert scores[1] == pytest.approx(0.0)


def test_apply_diversity_filter_limits_per_artist() -> None:
    ranked = [
        (_track("1", "A1", "Artist A"), 0.9),
        (_track("2", "A2", "Artist A"), 0.8),
        (_track("3", "B1", "Artist B"), 0.7),
        (_track("4", "A3", "Artist A"), 0.6),
    ]
    filtered = apply_diversity_filter(ranked, limit=3, max_per_artist=2)
    assert len(filtered) == 3
    assert sum(1 for track, _ in filtered if track.artists[0] == "Artist A") == 2


def test_fallback_scores_prefers_genre_and_reference_artist() -> None:
    profile = _profile()
    candidates = [
        _track("1", "Remote", "Unknown", genre="pop"),
        _track("2", "Nightcall", "Kavinsky", genre="synthwave"),
        _track("3", "Other", "Someone", genre="electronic"),
    ]
    ranked = fallback_scores(profile, candidates)
    assert ranked[0][0].id == "2"


@pytest.mark.asyncio
async def test_scoring_service_uses_embedding_rank(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ScoringService()
    candidates = [
        _track("1", "Low", "A"),
        _track("2", "High", "B"),
    ]

    def fake_rank(
        profile: MusicProfile,
        items: list[TrackCandidate],
        user_prompt: str | None,
    ) -> list[tuple[TrackCandidate, float]]:
        assert user_prompt == "test prompt"
        return [(items[1], 0.9), (items[0], 0.1)]

    monkeypatch.setattr(service, "_embedding_rank", fake_rank)

    tracks, method = await service.rank(_profile(), candidates, user_prompt="test prompt")
    assert method == "embedding"
    assert len(tracks) == 2
    assert tracks[0].id == "2"
    assert tracks[0].score == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_scoring_service_falls_back_when_model_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ScoringService()
    candidates = [
        _track("1", "Nightcall", "Kavinsky", genre="synthwave"),
        _track("2", "Other", "Unknown", genre="pop"),
    ]
    monkeypatch.setattr(service, "_embedding_rank", lambda *args, **kwargs: None)

    tracks, method = await service.rank(_profile(), candidates)
    assert method == "fallback"
    assert tracks[0].id == "1"


@pytest.mark.asyncio
async def test_scoring_service_respects_target_count() -> None:
    service = ScoringService()
    profile = _profile(target_track_count=3)
    candidates = [
        _track(str(i), f"T{i}", f"Artist {i % 2}", genre="synthwave")
        for i in range(10)
    ]
    monkeypatch_rank = [
        (track, float(10 - index) / 10)
        for index, track in enumerate(candidates)
    ]

    with patch.object(ScoringService, "_embedding_rank", return_value=monkeypatch_rank):
        tracks, _method = await service.rank(profile, candidates)

    assert len(tracks) == 3


def test_track_passport_format() -> None:
    track = TrackCandidate(
        id="1",
        title="Nightcall",
        artists=["Kavinsky"],
        album="OutRun",
        genre="synthwave",
        version="",
    )
    assert track.passport() == (
        "Название: Nightcall. "
        "Исполнитель: Kavinsky. "
        "Альбом: OutRun. "
        "Жанр: synthwave. "
        "Версия: "
    )
    assert track.embedding_passport() == "Nightcall. Kavinsky. synthwave"


def test_select_embedding_pool_uses_fallback_ranking() -> None:
    profile = _profile()
    candidates = [
        _track("1", "Remote", "Unknown", genre="pop"),
        _track("2", "Nightcall", "Kavinsky", genre="synthwave"),
        _track("3", "Other", "Someone", genre="electronic"),
    ]
    pool = select_embedding_pool(profile, candidates, limit=2)
    assert [track.id for track in pool] == ["2", "3"]


def test_reference_artist_boost() -> None:
    profile = _profile()
    ranked = [
        (_track("1", "Spam", "SEO Artist", genre="synthwave"), 0.90),
        (_track("2", "Nightcall", "Kavinsky", genre="synthwave"), 0.88),
    ]
    boosted = apply_reference_artist_boost(profile, ranked)
    assert boosted[0][0].id == "2"


def test_merge_embedding_rank_fills_diversity_pool() -> None:
    profile = _profile()
    embedded = [
        (_track(str(i), f"T{i}", f"Star {i // 2}", genre="synthwave"), 0.9 - i * 0.01)
        for i in range(18)
    ]
    tail = [_track(str(i + 100), f"Tail{i}", f"Extra {i}", genre="synthwave") for i in range(50)]
    candidates = [track for track, _ in embedded] + tail
    merged = merge_embedding_rank(profile, candidates, embedded)
    filtered = apply_diversity_filter(merged, limit=25, max_per_artist=2)
    assert len(filtered) == 25


@pytest.mark.asyncio
async def test_scoring_service_batch_embedding_with_mock_model() -> None:
    service = ScoringService()
    candidates = [_track("1", "A", "X"), _track("2", "B", "Y")]

    mock_model = MagicMock()
    mock_model.encode.return_value = np.array(
        [
            [1.0, 0.0],
            [1.0, 0.0],
            [0.0, 1.0],
        ]
    )

    with patch("app.services.scoring_service.get_embedding_model", return_value=mock_model):
        ranked = service._embedding_rank(_profile(), candidates, None)

    assert ranked is not None
    assert ranked[0][0].id == "1"
    assert ranked[0][1] == pytest.approx(1.0)
    mock_model.encode.assert_called_once()
    texts = mock_model.encode.call_args.args[0]
    assert texts[0].startswith("query:")
    assert texts[1].startswith("passage:")
