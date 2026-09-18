from app.schemas.llm import MusicProfile
from app.schemas.scoring import ScoredTrack
from app.schemas.track import TrackCandidate
from app.services.lyrics_filter import (
    apply_vocal_score_penalty,
    instrumental_lyrics_filter_needed,
    refine_instrumental_selection,
    swap_vocal_tracks_in_selection,
)
from app.utils.playlist_filters import filter_explicit_candidates, is_explicit_track


def _profile(*, vocal: str = "instrumental_only") -> MusicProfile:
    return MusicProfile(
        playlist_title="Focus",
        playlist_description="Instrumental",
        primary_genres=["ambient"],
        mood_tags=["calm"],
        vocal_type=vocal,
        reference_artists=["Tycho", "Bonobo", "Emancipator", "Helios"],
        search_queries=["ambient instrumental", "Tycho chill", "lo-fi beats"],
        target_track_count=3,
    )


def test_instrumental_lyrics_filter_needed() -> None:
    assert instrumental_lyrics_filter_needed(_profile()) is True
    assert instrumental_lyrics_filter_needed(_profile(vocal="any")) is False


def test_apply_vocal_score_penalty_reorders() -> None:
    ranked = [
        (TrackCandidate(id="1", title="A", artists=["X"]), 0.9),
        (TrackCandidate(id="2", title="B", artists=["Y"]), 0.85),
        (TrackCandidate(id="3", title="C", artists=["Z"]), 0.8),
    ]
    penalized = apply_vocal_score_penalty(ranked, {"1": True})
    assert penalized[0][0].id == "1"
    assert penalized[0][1] < 0.9
    assert penalized[1][0].id == "2"


def test_swap_vocal_tracks_in_selection() -> None:
    selected = [
        ScoredTrack.from_candidate(TrackCandidate(id="1", title="Vocal", artists=["A"]), 0.9),
        ScoredTrack.from_candidate(TrackCandidate(id="2", title="Ok", artists=["B"]), 0.8),
    ]
    ranked = [
        (TrackCandidate(id="1", title="Vocal", artists=["A"]), 0.9),
        (TrackCandidate(id="2", title="Ok", artists=["B"]), 0.8),
        (TrackCandidate(id="3", title="Inst", artists=["C"]), 0.7),
    ]
    refined, swaps = swap_vocal_tracks_in_selection(selected, ranked, {"1": True, "2": False})
    assert swaps == 1
    assert refined[0].id == "3"


def test_refine_instrumental_selection_emits_warning_when_vocal_remains() -> None:
    selected = [
        ScoredTrack.from_candidate(TrackCandidate(id="1", title="Vocal", artists=["A"]), 0.9),
    ]
    ranked = [(TrackCandidate(id="1", title="Vocal", artists=["A"]), 0.9)]
    _, warnings = refine_instrumental_selection(selected, ranked, {"1": True})
    assert any("осталось" in item for item in warnings)


def test_filter_explicit_candidates() -> None:
    tracks = [
        TrackCandidate(id="1", title="Clean", artists=["A"], explicit=False),
        TrackCandidate(id="2", title="Dirty", artists=["B"], explicit=True),
        TrackCandidate(id="3", title="Unknown", artists=["C"], explicit=None),
    ]
    kept = filter_explicit_candidates(tracks)
    assert [track.id for track in kept] == ["1", "3"]
    assert is_explicit_track(tracks[1]) is True
