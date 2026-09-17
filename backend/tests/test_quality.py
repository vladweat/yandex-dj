from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate
from app.utils.quality import (
    artist_matches_reference,
    is_arrangement,
    is_spurious_track,
    normalize_song_title,
)


def _profile() -> MusicProfile:
    return MusicProfile(
        playlist_title="Night Drive",
        playlist_description="Dark synthwave for coding",
        primary_genres=["synthwave"],
        mood_tags=["dark"],
        vocal_type="any",
        reference_artists=["Kavinsky", "Gunship", "The Midnight", "FM-84"],
        search_queries=["synthwave night", "dark synth", "retrowave"],
        target_track_count=25,
    )


def test_spurious_cover_in_title() -> None:
    track = TrackCandidate(id="1", title="Nightcall (Kavinsky Cover)", artists=["Barcelona 82"])
    assert is_spurious_track(track, _profile()) is True


def test_spurious_arrangement_piano_version() -> None:
    track = TrackCandidate(
        id="a1",
        title="Cornfield Chase - Piano Version",
        artists=["Sjors Weijermars, Hans Zimmer"],
    )
    assert is_arrangement(track) is True
    assert is_spurious_track(track, _profile()) is True


def test_spurious_compilation_artist() -> None:
    track = TrackCandidate(
        id="c1",
        title="Honor Him",
        artists=["Soundtrack & Theme Orchestra, The Gym All-Stars"],
    )
    assert is_spurious_track(track, _profile()) is True


def test_spurious_reference_in_title_only() -> None:
    track = TrackCandidate(id="2", title="Nightcall - Kavinsky", artists=["Eewas Cesium"])
    assert is_spurious_track(track, _profile()) is True


def test_spurious_reference_name_as_title() -> None:
    track = TrackCandidate(id="3", title="Gunship", artists=["Kasper"])
    assert is_spurious_track(track, _profile()) is True


def test_valid_reference_collaboration() -> None:
    track = TrackCandidate(id="4", title="Silence", artists=["Essenger, The Midnight"])
    assert is_spurious_track(track, _profile()) is False


def test_valid_reference_artist_track() -> None:
    track = TrackCandidate(id="5", title="Nightcall", artists=["Kavinsky"])
    assert is_spurious_track(track, _profile()) is False


def test_normalize_song_title_strips_suffix() -> None:
    assert normalize_song_title("Nightcall - Kavinsky") == "nightcall"
    assert normalize_song_title("Nightcall (Kavinsky Cover)") == "nightcall"


def test_spurious_functional_seo_vibe_for_title() -> None:
    track = TrackCandidate(
        id="seo1",
        title="Inspired Saxophone Bossa Nova - Vibe for Cooking",
        artists=["Music for Cooking Moods"],
    )
    assert is_spurious_track(track, _profile()) is True


def test_spurious_functional_seo_cooking_artist() -> None:
    track = TrackCandidate(
        id="seo2",
        title="Lightenup",
        artists=["Cooking Jazz Moods"],
    )
    assert is_spurious_track(track, _profile()) is True


def test_valid_real_track_not_seo() -> None:
    track = TrackCandidate(id="ok1", title="Lightenup", artists=["Parcels"])
    assert is_spurious_track(track, _profile()) is False


def test_spurious_functional_seo_sleep_context() -> None:
    track = TrackCandidate(
        id="seo3",
        title="Peaceful Piano - Music for Sleeping",
        artists=["Sleep Music"],
    )
    assert is_spurious_track(track, _profile()) is True


def test_spurious_functional_seo_study_vibe_for() -> None:
    track = TrackCandidate(
        id="seo4",
        title="Calm Lo-Fi Beats - Vibe for Studying",
        artists=["Study Beats Playlist"],
    )
    assert is_spurious_track(track, _profile()) is True


def test_spurious_functional_seo_workout_artist() -> None:
    track = TrackCandidate(
        id="seo5",
        title="Pump It",
        artists=["Workout Music"],
    )
    assert is_spurious_track(track, _profile()) is True


def test_valid_music_for_airports_by_real_artist() -> None:
    track = TrackCandidate(id="eno", title="Music for Airports", artists=["Brian Eno"])
    assert is_spurious_track(track, _profile()) is False


def test_spurious_genre_descriptor_title() -> None:
    track = TrackCandidate(id="g1", title="Upbeat Indie Pop", artists=["Alexey Maximov"])
    assert is_spurious_track(track, _profile()) is True


def test_spurious_genre_descriptor_title_single_word() -> None:
    track = TrackCandidate(id="g2", title="Indie", artists=["Roman Vorster"])
    assert is_spurious_track(track, _profile()) is True


def test_spurious_seo_label_artist() -> None:
    track = TrackCandidate(id="g3", title="Track 1", artists=["Vinyl Sounds"])
    assert is_spurious_track(track, _profile()) is True


def test_valid_creative_title_and_real_artist() -> None:
    track = TrackCandidate(id="g4", title="Крымский инди-поп", artists=["Эді"])
    assert is_spurious_track(track, _profile()) is False


def test_valid_khruangbin_track() -> None:
    track = TrackCandidate(id="g5", title="Maria También", artists=["Khruangbin"])
    assert is_spurious_track(track, _profile()) is False


def test_valid_single_word_cozy_title() -> None:
    track = TrackCandidate(id="g6", title="Cozy", artists=["Camyo"])
    assert is_spurious_track(track, _profile()) is False


def test_spurious_soundtrack_artist_ru() -> None:
    track = TrackCandidate(id="g7", title="Now You Has Jazz", artists=["саундтрек"])
    assert is_spurious_track(track, _profile()) is True


def test_spurious_genre_stack_with_groove() -> None:
    track = TrackCandidate(id="g8", title="Indie Pop Groove", artists=["James Smith"])
    assert is_spurious_track(track, _profile()) is True


def test_spurious_inspiring_indie_pop() -> None:
    track = TrackCandidate(id="g9", title="Inspiring Indie Pop", artists=["Assai"])
    assert is_spurious_track(track, _profile()) is True


def test_artist_matches_reference_exact_only() -> None:
    assert artist_matches_reference("Parcels", "Parcels") is True
    assert artist_matches_reference("Parcel", "Parcels") is False
    assert artist_matches_reference("Essenger, The Midnight", "The Midnight") is True


def test_spurious_reference_near_title_parcel() -> None:
    profile = _profile().model_copy(update={"reference_artists": ["Parcels", "Khruangbin"]})
    track = TrackCandidate(id="p1", title="Parcel", artists=["Vritra"])
    assert is_spurious_track(track, profile) is True


def test_spurious_mood_keyword_artist() -> None:
    track = TrackCandidate(id="p2", title="5x", artists=["COZY YiELDS"])
    assert is_spurious_track(track, _profile()) is True


def test_spurious_indie_prefix_title() -> None:
    track = TrackCandidate(id="p3", title="Indie Mindy", artists=["Fab Claxton"])
    assert is_spurious_track(track, _profile()) is True


def test_spurious_mood_keyword_title() -> None:
    track = TrackCandidate(id="p4", title="Cozy Forever", artists=["Kembe X"])
    assert is_spurious_track(track, _profile()) is True


def test_spurious_genre_suffix_artist() -> None:
    track = TrackCandidate(id="p5", title="Micro Dust", artists=["Waco Texas Metal"])
    assert is_spurious_track(track, _profile()) is True


def test_spurious_sad_rap_title() -> None:
    track = TrackCandidate(id="p6", title="Sad Rap", artists=["Musical Kay"])
    assert is_spurious_track(track, _profile()) is True


def test_spurious_get_est_rap_title() -> None:
    track = TrackCandidate(id="p7", title="Get Est Rap", artists=["DISTXRD"])
    assert is_spurious_track(track, _profile()) is True


def test_spurious_melancholy_mood_artist() -> None:
    track = TrackCandidate(id="p8", title="White Kids", artists=["Melancholy Mø"])
    assert is_spurious_track(track, _profile()) is True


def test_valid_real_underground_rap_track() -> None:
    track = TrackCandidate(id="p9", title="Kronol", artists=["Ghostemane"])
    assert is_spurious_track(track, _profile()) is False


def test_valid_bones_track() -> None:
    track = TrackCandidate(id="p10", title="Suffer", artists=["BONES", "xavier wulf"])
    assert is_spurious_track(track, _profile()) is False


def test_spurious_type_beat_title() -> None:
    track = TrackCandidate(
        id="p11",
        title="'M' Emo rap type beat",
        artists=["鸣久"],
    )
    assert is_spurious_track(track, _profile()) is True


def test_spurious_genre_stack_marketing_title() -> None:
    track = TrackCandidate(
        id="p12",
        title="emo rap for losers to cry to",
        artists=["plumbers incorporated"],
    )
    assert is_spurious_track(track, _profile()) is True


def test_spurious_asterisk_genre_stack_title() -> None:
    track = TrackCandidate(
        id="p13",
        title="Asterisk Gang Emo Rap",
        artists=["Greenland Shark"],
    )
    assert is_spurious_track(track, _profile()) is True


def test_spurious_single_genre_word_title() -> None:
    track = TrackCandidate(id="p14", title="Emo", artists=["Mistah F.A.B."])
    assert is_spurious_track(track, _profile()) is True


def test_spurious_near_dup_reference_in_title() -> None:
    profile = _profile().model_copy(
        update={"reference_artists": ["Ghostemane", "Kavinsky", "Gunship", "FM-84"]}
    )
    track = TrackCandidate(id="p15", title="ghostmane", artists=["Haiyti"])
    assert is_spurious_track(track, profile) is True


def test_spurious_reference_split_title_artist() -> None:
    profile = _profile().model_copy(
        update={"reference_artists": ["Night Lovell", "Kavinsky", "Gunship", "FM-84"]}
    )
    track = TrackCandidate(id="p16", title="Night Ride", artists=["Lovell Lykaon"])
    assert is_spurious_track(track, profile) is True


def test_valid_real_artist_with_night_in_title() -> None:
    """Обычный трек с Night в названии у реального не-якоря — ок."""
    profile = _profile().model_copy(
        update={"reference_artists": ["Kavinsky", "Gunship", "The Midnight", "FM-84"]}
    )
    track = TrackCandidate(id="p17", title="Nightcall", artists=["Kavinsky"])
    assert is_spurious_track(track, profile) is False
