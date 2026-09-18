from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate
from app.utils.prompt_constraints import (
    artists_mentioned_in_prompt,
    ensure_hard_reference_artists,
    extract_prompt_constraints,
    filter_excluded_languages,
    resolve_hard_reference_artists,
)


def _profile() -> MusicProfile:
    return MusicProfile(
        playlist_title="Cloud",
        playlist_description="Sad rap",
        primary_genres=["hip hop", "trap"],
        mood_tags=["sad", "melancholic"],
        vocal_type="vocal_only",
        reference_artists=["Bones", "$uicideboy$", "Night Lovell", "Lil Peep"],
        search_queries=["Bones", "$uicideboy$", "Night Lovell"],
        target_track_count=25,
    )


def test_extract_diversity_and_exclude_ru() -> None:
    constraints = extract_prompt_constraints(
        "грустить под Bones, исключи русские треки, сделай плейлист разнообразным"
    )
    assert constraints.prefer_high_diversity is True
    assert constraints.exclude_languages == ["ru"]
    assert constraints.exclude_explicit is False


def test_extract_exclude_explicit_from_prompt() -> None:
    constraints = extract_prompt_constraints("вечеринка без мата и нецензурщины")
    assert constraints.exclude_explicit is True


def test_extract_no_constraints_on_plain_prompt() -> None:
    constraints = extract_prompt_constraints("под настроение пока варю макароны")
    assert constraints.prefer_high_diversity is False
    assert constraints.exclude_languages == []


def test_artists_mentioned_in_prompt() -> None:
    mentioned = artists_mentioned_in_prompt(
        "хочется грустить под Bones и Night Lovell",
        _profile().reference_artists,
    )
    assert "Bones" in mentioned
    assert "Night Lovell" in mentioned


def test_resolve_hard_from_prompt_mentions() -> None:
    hard = resolve_hard_reference_artists(
        _profile(),
        "американский реп по типу Bones",
    )
    assert hard == ["Bones"]


def test_resolve_hard_uses_declared_field() -> None:
    profile = _profile().model_copy(update={"hard_reference_artists": ["$uicideboy$", "Bones"]})
    hard = resolve_hard_reference_artists(profile, "что угодно")
    assert hard == ["$uicideboy$", "Bones"]


def test_resolve_hard_fallback_top_two() -> None:
    hard = resolve_hard_reference_artists(_profile(), "грустная музыка без имён")
    assert hard == ["Bones", "$uicideboy$"]


def test_ensure_hard_reference_artists_persists() -> None:
    updated = ensure_hard_reference_artists(
        _profile(),
        "реп как Bones",
    )
    assert updated.hard_reference_artists == ["Bones"]


def test_filter_excluded_languages_drops_cyrillic() -> None:
    tracks = [
        TrackCandidate(id="1", title="Suffer", artists=["BONES"]),
        TrackCandidate(id="2", title="Имя", artists=["Скриптонит"]),
        TrackCandidate(id="3", title="Night Life", artists=["Yanix", "ЛСП"]),
        TrackCandidate(id="4", title="Kronol", artists=["Ghostemane"]),
    ]
    kept = filter_excluded_languages(tracks, ["ru"])
    assert [track.id for track in kept] == ["1", "4"]
