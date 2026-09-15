from app.schemas.llm import MusicProfile
from app.utils.search_queries import (
    expand_search_queries,
    is_generic_search_query,
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


def test_refine_search_queries_removes_generic_and_adds_artists() -> None:
    refined = refine_search_queries(_profile())
    assert all(not is_generic_search_query(q) for q in refined.search_queries)
    assert any("Tycho" in q for q in refined.search_queries)
    assert len(refined.search_queries) >= 3


def test_expand_search_queries_second_pass() -> None:
    used = {q.lower() for q in _profile().search_queries}
    first = expand_search_queries(_profile(), used=used, pass_num=0)
    second = expand_search_queries(_profile(), used=used, pass_num=1)
    assert first
    assert second
    assert first != second
