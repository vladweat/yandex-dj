from app.schemas.llm import MusicProfile
from app.utils.search_queries import (
    expand_search_queries,
    is_generic_search_query,
    is_mood_bait_search_query,
    is_rejected_search_query,
    refine_search_queries,
)


def _profile() -> MusicProfile:
    return MusicProfile(
        playlist_title="Night Focus",
        playlist_description="Calm ambient for coding",
        primary_genres=["ambient", "lo-fi"],
        mood_tags=["calm", "focused"],
        vocal_type="instrumental_only",
        reference_artists=["Tycho", "Nujabes", "Bonobo", "Helios"],
        search_queries=[
            "ambient coding night",
            "lo-fi beats study",
            "instrumental chill focus",
        ],
        target_track_count=25,
    )


def test_is_generic_search_query() -> None:
    assert is_generic_search_query("lo-fi coding music")
    assert is_generic_search_query("workout playlist upbeat")
    assert is_generic_search_query("bossa nova cooking")
    assert is_generic_search_query("vibe for sleep")
    assert is_generic_search_query("music for studying")
    assert is_generic_search_query("lo-fi studying")
    assert not is_generic_search_query("Tycho ambient instrumental")
    assert not is_generic_search_query("Nujabes chillhop")
    assert not is_generic_search_query("cozy kitchen indie")


def test_is_mood_bait_search_query() -> None:
    assert is_mood_bait_search_query("Bones sad rap")
    assert is_mood_bait_search_query("sad rap")
    assert is_mood_bait_search_query("$uicideboy$ emotional")
    assert is_mood_bait_search_query("Khruangbin chill")
    assert is_mood_bait_search_query("Men I Trust cozy")
    assert is_mood_bait_search_query("emotional trap")
    assert not is_mood_bait_search_query("Bones")
    assert not is_mood_bait_search_query("Tycho ambient")
    assert not is_mood_bait_search_query("Nujabes chillhop")
    assert not is_mood_bait_search_query("dark synth instrumental")
    assert not is_mood_bait_search_query("cloud rap underground")


def test_is_genre_only_search_query() -> None:
    from app.utils.search_queries import is_genre_only_search_query

    assert is_genre_only_search_query("emo rap")
    assert is_genre_only_search_query("indie pop")
    assert is_genre_only_search_query("ambient")
    assert is_genre_only_search_query("hip hop")
    assert not is_genre_only_search_query("Bones")
    assert not is_genre_only_search_query("Tycho ambient")
    assert not is_genre_only_search_query("Parcels indie pop")
    assert not is_genre_only_search_query("cloud rap underground")


def test_refine_drops_genre_only_queries() -> None:
    profile = MusicProfile(
        playlist_title="Cloud",
        playlist_description="Underground",
        primary_genres=["hip hop", "trap", "emo rap"],
        mood_tags=["sad"],
        vocal_type="vocal_only",
        reference_artists=["Bones", "$uicideboy$", "Night Lovell", "Lil Peep"],
        search_queries=["Bones", "$uicideboy$", "emo rap"],
        target_track_count=25,
    )
    refined = refine_search_queries(profile)
    assert all(not is_rejected_search_query(q) for q in refined.search_queries)
    assert not any(q.lower() == "emo rap" for q in refined.search_queries)
    assert "Bones" in refined.search_queries


def test_refine_search_queries_removes_generic_and_mood_bait() -> None:
    profile = MusicProfile(
        playlist_title="Sad Cloud",
        playlist_description="Sad American underground rap",
        primary_genres=["hip hop", "trap", "emo rap"],
        mood_tags=["sad", "melancholic", "introspective"],
        vocal_type="vocal_only",
        reference_artists=["Bones", "$uicideboy$", "Night Lovell", "Lil Peep"],
        search_queries=[
            "Bones sad rap",
            "$uicideboy$ emotional",
            "Night Lovell introspective",
            "Lil Peep melancholic",
            "Bones",
        ],
        target_track_count=25,
    )
    refined = refine_search_queries(profile)
    assert all(not is_rejected_search_query(q) for q in refined.search_queries)
    assert "Bones" in refined.search_queries
    assert not any("sad" in q.lower() for q in refined.search_queries)
    assert len(refined.search_queries) >= 3


def test_refine_search_queries_removes_generic_and_adds_artists() -> None:
    refined = refine_search_queries(_profile())
    assert all(not is_rejected_search_query(q) for q in refined.search_queries)
    assert any("Tycho" in q for q in refined.search_queries)
    assert len(refined.search_queries) >= 3


def test_expand_search_queries_second_pass() -> None:
    used = {q.lower() for q in _profile().search_queries}
    first = expand_search_queries(_profile(), used=used, pass_num=0)
    second = expand_search_queries(_profile(), used=used, pass_num=1)
    assert first
    assert second
    assert first != second
    assert all(not is_rejected_search_query(q) for q in first + second)


def test_expand_does_not_emit_artist_mood() -> None:
    used: set[str] = set()
    profile = _profile().model_copy(
        update={
            "mood_tags": ["sad", "cozy"],
            "reference_artists": ["Bones", "Tycho"],
            "primary_genres": ["rap", "ambient"],
        }
    )
    extra = expand_search_queries(profile, used=used, pass_num=1)
    assert not any("sad" in q.lower() or "cozy" in q.lower() for q in extra)
