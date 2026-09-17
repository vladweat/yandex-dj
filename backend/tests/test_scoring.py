from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate
from app.services.scoring_service import ScoringService
from app.utils.scoring import (
    adaptive_score_floor,
    apply_diversity_filter,
    apply_library_artist_boost,
    apply_reference_anchor_boost,
    build_prompt_text,
    candidates_for_embedding,
    cosine_scores,
    fallback_scores,
    filter_by_top_median_gap,
    is_score_plateau,
    max_anchor_tracks,
    max_tracks_per_artist,
    merge_embedding_rank,
    select_playlist_tracks,
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
    assert max_tracks_per_artist(25, configured=1) == 1
    assert max_tracks_per_artist(30, configured=2) == 3


def test_max_anchor_tracks_is_about_sixty_percent() -> None:
    assert max_anchor_tracks(25) == 15
    assert max_anchor_tracks(10) == 6
    assert max_anchor_tracks(1) == 1


def test_filter_by_top_median_gap_drops_embedding_false_positive() -> None:
    ranked = [
        (_track(str(i), f"T{i}", f"A{i}"), 0.94 - i * 0.005) for i in range(10)
    ]
    ranked.append((_track("junk", "Vlone", "Hauvy"), 0.70))
    filtered = filter_by_top_median_gap(ranked)
    assert all(track.id != "junk" for track, _ in filtered)
    assert len(filtered) == 10


def test_filter_by_top_median_gap_keeps_near_core() -> None:
    ranked = [(_track(str(i), f"T{i}", f"A{i}"), 0.90 - i * 0.01) for i in range(12)]
    filtered = filter_by_top_median_gap(ranked)
    assert len(filtered) == 12


def test_build_prompt_text_prioritizes_user_prompt_not_reference_artists() -> None:
    text = build_prompt_text(_profile(), user_prompt="пока карю макароны")
    assert "пока карю макароны" in text
    assert "Dark synthwave for coding" in text
    assert "Kavinsky" not in text


def test_cosine_scores_identical_vectors() -> None:
    vec = np.array([1.0, 0.0, 0.0])
    docs = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    scores = cosine_scores(vec, docs)
    assert scores[0] == pytest.approx(1.0)
    assert scores[1] == pytest.approx(0.0)


def test_candidates_for_embedding_all_when_limit_zero() -> None:
    candidates = [_track(str(i), f"T{i}", "A") for i in range(5)]
    assert len(candidates_for_embedding(candidates, limit=0)) == 5


def test_adaptive_score_floor_detects_cliff() -> None:
    scores = [0.92, 0.9, 0.89, 0.75, 0.74]
    floor = adaptive_score_floor(scores, limit=4)
    assert floor == pytest.approx(0.75 - 1e-6)


def test_adaptive_score_floor_soft_when_no_cliff() -> None:
    scores = [0.92, 0.91, 0.9, 0.89, 0.88]
    floor = adaptive_score_floor(scores, limit=25)
    assert floor == pytest.approx(0.88 - 1e-6)


def test_apply_diversity_filter_counts_all_listed_artists() -> None:
    ranked = [
        (
            TrackCandidate(id="1", title="T1", artists=["Sjors Weijermars", "Hans Zimmer"]),
            0.92,
        ),
        (
            TrackCandidate(id="2", title="T2", artists=["Music Lab Collective", "Hans Zimmer"]),
            0.91,
        ),
        (_track("3", "Original", "Hans Zimmer"), 0.9),
        (_track("4", "Other", "Max Richter"), 0.89),
    ]
    filtered = apply_diversity_filter(ranked, limit=4, max_per_artist=2)
    assert len(filtered) == 3


def test_apply_diversity_filter_allows_extra_anchor_slots() -> None:
    profile = _profile()
    ranked = [
        (_track("1", "A1", "Kavinsky"), 0.9),
        (_track("2", "A2", "Kavinsky"), 0.89),
        (_track("3", "A3", "Kavinsky"), 0.88),
        (_track("4", "B1", "Other"), 0.87),
    ]
    filtered = apply_diversity_filter(
        ranked,
        limit=4,
        max_per_artist=2,
        profile=profile,
        anchor_max_per_artist=3,
    )
    assert len(filtered) == 4
    assert sum(1 for track, _ in filtered if track.artists[0] == "Kavinsky") == 3


def test_soft_reference_artists_use_normal_diversity_slots() -> None:
    profile = _profile().model_copy(
        update={
            "hard_reference_artists": ["Kavinsky"],
            "reference_artists": [
                "Kavinsky",
                "Perturbator",
                "Night Lovell",
                "Lil Peep",
            ],
        }
    )
    ranked = [
        (_track("1", "A1", "Night Lovell"), 0.9),
        (_track("2", "A2", "Night Lovell"), 0.89),
        (_track("3", "A3", "Night Lovell"), 0.88),
        (_track("4", "B1", "Other"), 0.87),
    ]
    filtered = apply_diversity_filter(
        ranked,
        limit=4,
        max_per_artist=2,
        profile=profile,
        anchor_max_per_artist=3,
    )
    assert sum(1 for track, _ in filtered if track.artists[0] == "Night Lovell") == 2


def test_hard_anchor_boost_skips_soft_refs() -> None:
    profile = _profile().model_copy(
        update={
            "hard_reference_artists": ["Kavinsky"],
            "reference_artists": [
                "Kavinsky",
                "Perturbator",
                "Night Lovell",
                "Lil Peep",
            ],
        }
    )
    ranked = [
        (_track("1", "A", "Night Lovell"), 0.80),
        (_track("2", "B", "Kavinsky"), 0.80),
    ]
    boosted = apply_reference_anchor_boost(ranked, profile)
    by_id = {track.id: score for track, score in boosted}
    assert by_id["2"] == pytest.approx(0.83)
    assert by_id["1"] == pytest.approx(0.80)


def test_mood_title_demote_lowers_sad_title() -> None:
    from app.utils.scoring import apply_mood_title_demote

    profile = _profile().model_copy(update={"mood_tags": ["sad", "melancholic"]})
    ranked = [
        (_track("1", "Sad Night", "Random"), 0.85),
        (_track("2", "Waves", "Other"), 0.849),
    ]
    demoted = apply_mood_title_demote(ranked, profile)
    assert demoted[0][0].id == "2"
    assert demoted[1][0].id == "1"


def test_plateau_prefers_non_hard_anchor_in_bucket() -> None:
    from app.utils.scoring import prefer_non_anchors_on_plateau

    profile = _profile(target_track_count=5).model_copy(
        update={
            "hard_reference_artists": ["Kavinsky"],
            "reference_artists": [
                "Kavinsky",
                "Perturbator",
                "Gunship",
                "FM-84",
            ],
        }
    )
    ranked = [
        (_track("1", "A", "Kavinsky"), 0.850),
        (_track("2", "B", "Ghostemane"), 0.849),
        (_track("3", "C", "Someone"), 0.848),
        (_track("4", "D", "Else"), 0.847),
        (_track("5", "E", "Other"), 0.846),
    ]
    assert is_score_plateau(ranked, 5)
    reordered = prefer_non_anchors_on_plateau(ranked, profile, limit=5)
    # В одной score-корзине все non-hard раньше hard (Kavinsky).
    assert reordered[0][0].id == "2"
    assert reordered[-1][0].id == "1"
    assert all(track.artists[0] != "Kavinsky" for track, _ in reordered[:-1])


def test_select_playlist_tracks_sorted_by_score_after_fill() -> None:
    profile = _profile(target_track_count=4)
    ranked = [
        (_track("1", "A1", "Khruangbin"), 0.9),
        (_track("2", "A2", "Khruangbin"), 0.89),
        (_track("3", "A3", "Khruangbin"), 0.88),
        (_track("4", "B1", "Parcels"), 0.87),
        (_track("5", "B2", "Parcels"), 0.86),
        (_track("6", "C1", "Other"), 0.7),
    ]
    selected = select_playlist_tracks(ranked, profile)
    scores = [score for _, score in selected]
    assert scores == sorted(scores, reverse=True)


def test_select_playlist_tracks_high_diversity_limits_per_artist() -> None:
    profile = _profile(target_track_count=4)
    ranked = [
        (_track("1", "A", "Artist1"), 0.95),
        (_track("2", "B", "Artist1"), 0.94),
        (_track("3", "C", "Artist2"), 0.93),
        (_track("4", "D", "Artist3"), 0.92),
        (_track("5", "E", "Artist4"), 0.91),
    ]
    selected = select_playlist_tracks(ranked, profile, diversity="high")
    artists = [track.artists[0] for track, _ in selected]
    assert artists.count("Artist1") == 1
    assert len(selected) == 4


def test_select_playlist_tracks_fills_when_elbow_blocks_but_pool_large() -> None:
    profile = _profile(target_track_count=5)
    ranked = [
        (_track("1", "A1", "Khruangbin"), 0.9),
        (_track("2", "A2", "Khruangbin"), 0.89),
        (_track("3", "A3", "Khruangbin"), 0.88),
        (_track("4", "B1", "Parcels"), 0.87),
        (_track("5", "B2", "Parcels"), 0.86),
        (_track("6", "B3", "Parcels"), 0.85),
        (_track("7", "C1", "Men I Trust"), 0.7),
        (_track("8", "C2", "Men I Trust"), 0.69),
    ]
    selected = select_playlist_tracks(ranked, profile)
    assert len(selected) == 5


def test_select_playlist_tracks_uses_adaptive_floor() -> None:
    profile = _profile(target_track_count=3)
    ranked = [
        (_track("1", "A", "Artist 0"), 0.9),
        (_track("2", "B", "Artist 1"), 0.89),
        (_track("3", "C", "Artist 2"), 0.88),
        (_track("4", "D", "Artist 3"), 0.5),
    ]
    selected = select_playlist_tracks(ranked, profile)
    assert len(selected) == 3
    assert {track.id for track, _ in selected} == {"1", "2", "3"}


def test_select_playlist_tracks_fills_past_anchor_concentrated_top() -> None:
    """Топ-N по score = одни якоря; fill должен добрать других артистов ниже scores[N-1]."""
    profile = MusicProfile(
        playlist_title="Kitchen",
        playlist_description="cozy",
        primary_genres=["indie"],
        mood_tags=["cozy"],
        vocal_type="any",
        reference_artists=["Parcels", "Khruangbin", "Men I Trust", "Camyo"],
        search_queries=["indie cozy", "chill groove", "soft funk"],
        target_track_count=10,
    )
    ranked: list[tuple[TrackCandidate, float]] = []
    score = 0.87
    for artist in ("Parcels", "Khruangbin", "Men I Trust"):
        for index in range(8):
            ranked.append((_track(f"{artist}-{index}", f"T{index}", artist), score))
            score -= 0.0005
    # Чуть ниже «сырого» 10-го score, но в пределах tail drop от последнего selected.
    extras = [
        ("Soulive", "Waves"),
        ("Pompeya", "Power"),
        ("Toro y Moi", "Rose"),
        ("Unknown Mortal Orchestra", "Multi-Love"),
    ]
    for index, (artist, title) in enumerate(extras):
        ranked.append((_track(f"x{index}", title, artist), 0.84 - index * 0.002))

    selected = select_playlist_tracks(ranked, profile)
    assert len(selected) == 10
    artists = {track.artists[0] for track, _ in selected}
    assert artists & {"Soulive", "Pompeya", "Toro y Moi", "Unknown Mortal Orchestra"}


def test_select_playlist_tracks_caps_anchor_share() -> None:
    profile = MusicProfile(
        playlist_title="Kitchen",
        playlist_description="cozy",
        primary_genres=["indie"],
        mood_tags=["cozy"],
        vocal_type="any",
        reference_artists=["Parcels", "Khruangbin", "Men I Trust", "Camyo"],
        search_queries=["indie cozy", "chill groove", "soft funk"],
        target_track_count=10,
    )
    ranked: list[tuple[TrackCandidate, float]] = []
    score = 0.95
    for artist in ("Parcels", "Khruangbin", "Men I Trust", "Camyo"):
        for index in range(5):
            ranked.append((_track(f"{artist}-{index}", f"T{index}", artist), score))
            score -= 0.001
    for index in range(20):
        ranked.append((_track(f"n{index}", f"N{index}", f"Other {index}"), score))
        score -= 0.001

    selected = select_playlist_tracks(ranked, profile)
    assert len(selected) == 10
    anchors = sum(
        1
        for track, _ in selected
        if track.artists[0] in {"Parcels", "Khruangbin", "Men I Trust", "Camyo"}
    )
    assert anchors <= max_anchor_tracks(10)


def test_select_playlist_tracks_drops_far_tail_false_positive() -> None:
    profile = _profile(target_track_count=10)
    ranked = [
        (_track(str(i), f"Good {i}", f"Artist {i}", genre="synthwave"), 0.92 - i * 0.005)
        for i in range(15)
    ]
    ranked.append((_track("bad", "Vlone", "Hauvy", genre="trap"), 0.70))
    selected = select_playlist_tracks(ranked, profile)
    assert all(track.id != "bad" for track, _ in selected)
    assert len(selected) == 10


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
    candidates = [_track("1", "Low", "A"), _track("2", "High", "B")]

    def fake_rank(
        profile: MusicProfile,
        items: list[TrackCandidate],
        user_prompt: str | None,
    ) -> list[tuple[TrackCandidate, float]]:
        return [(items[1], 0.9), (items[0], 0.85)]

    monkeypatch.setattr(service, "_embedding_rank", fake_rank)
    tracks, method = await service.rank(_profile(), candidates, user_prompt="test")
    assert method == "embedding"
    assert tracks[0].id == "2"


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
    candidates = [_track(str(i), f"T{i}", f"Artist {i % 2}", genre="synthwave") for i in range(10)]
    monkeypatch_rank = [(track, 0.95 - index * 0.01) for index, track in enumerate(candidates)]

    with patch.object(ScoringService, "_embedding_rank", return_value=monkeypatch_rank):
        tracks, _method = await service.rank(profile, candidates)

    assert len(tracks) == 3


def test_apply_reference_anchor_boost_promotes_anchor_artist() -> None:
    profile = _profile()
    ranked = [
        (_track("1", "Other", "Unknown"), 0.86),
        (_track("2", "Nightcall", "Kavinsky"), 0.84),
    ]
    boosted = apply_reference_anchor_boost(ranked, profile)
    assert boosted[0][0].id == "2"


def test_apply_library_artist_boost_promotes_library_artist() -> None:
    ranked = [
        (_track("1", "Other", "Unknown Band"), 0.86),
        (_track("2", "Hit", "My Fav Artist"), 0.84),
    ]
    boosted = apply_library_artist_boost(ranked, ["My Fav Artist"], boost=0.05)
    assert boosted[0][0].id == "2"
    assert boosted[0][1] == pytest.approx(0.89)


def test_merge_embedding_rank_uses_only_embedded_scores() -> None:
    profile = _profile()
    embedded = [
        (_track("1", "High", "Star A", genre="synthwave"), 0.95),
        (_track("2", "Mid", "Star B", genre="synthwave"), 0.85),
    ]
    tail = [_track("99", "Tail", "Extra", genre="synthwave")]
    candidates = [track for track, _ in embedded] + tail
    merged = merge_embedding_rank(profile, candidates, embedded)
    assert [track.id for track, _ in merged] == ["1", "2"]


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


@pytest.mark.asyncio
async def test_scoring_service_rank_pool_merge_embeds_only_new(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ScoringService()
    existing = [(_track("1", "Old", "A"), 0.9)]
    new_tracks = [_track("2", "New", "B"), _track("1", "Dup", "A")]

    def fake_rank(
        profile: MusicProfile,
        items: list[TrackCandidate],
        user_prompt: str | None,
    ) -> list[tuple[TrackCandidate, float]]:
        assert [track.id for track in items] == ["2"]
        return [(items[0], 0.95)]

    monkeypatch.setattr(service, "_embedding_rank", fake_rank)
    merged, method = await service.rank_pool_merge(
        _profile(),
        existing,
        new_tracks,
        user_prompt="test",
    )
    assert method == "embedding"
    assert [track.id for track, _ in merged] == ["2", "1"]
    assert merged[0][1] == pytest.approx(0.95)
