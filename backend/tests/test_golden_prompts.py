"""Golden smoke: kitchen / coding / synthwave — mock scores, без LLM/Yandex."""

from __future__ import annotations

from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate
from app.utils.quality import is_spurious_track
from app.utils.scoring import select_playlist_tracks
from app.utils.search_queries import is_generic_search_query

GOLDEN_PROMPTS = {
    "kitchen": "под настроение пока варю макароны",
    "coding": "спокойная музыка для кодинга поздней ночью",
    "synthwave": "саундтрек для ночной поездки в стиле синтвейв",
}


def _kitchen_profile() -> MusicProfile:
    return MusicProfile(
        playlist_title="Кухонный вайб",
        playlist_description="Лёгкая уютная музыка для спокойной готовки",
        primary_genres=["indie pop", "bossa nova", "chill"],
        mood_tags=["cozy", "warm", "relaxed", "domestic"],
        vocal_type="any",
        reference_artists=["Khruangbin", "Men I Trust", "Parcels", "Angus & Julia Stone"],
        search_queries=[
            "Khruangbin chill",
            "Men I Trust cozy",
            "Parcels indie pop",
        ],
        target_track_count=25,
    )


def _coding_profile() -> MusicProfile:
    return MusicProfile(
        playlist_title="Ночной фокус",
        playlist_description="Спокойный эмбиент и лоу-фай для глубокой концентрации",
        primary_genres=["ambient", "lo-fi", "downtempo"],
        mood_tags=["calm", "focused", "nocturnal", "minimal"],
        vocal_type="instrumental_only",
        reference_artists=["Tycho", "Nujabes", "Bonobo", "Helios"],
        search_queries=[
            "Tycho ambient instrumental",
            "Nujabes chillhop",
            "lo-fi hip hop instrumental",
        ],
        target_track_count=25,
    )


def _synthwave_profile() -> MusicProfile:
    return MusicProfile(
        playlist_title="Ночной неон",
        playlist_description="Синтвейв для ночной поездки",
        primary_genres=["synthwave", "retrowave"],
        mood_tags=["nocturnal", "atmospheric"],
        vocal_type="any",
        reference_artists=["Kavinsky", "Perturbator", "Gunship", "Timecop1983"],
        search_queries=[
            "synthwave night drive",
            "retrowave neon",
            "dark synth instrumental",
        ],
        target_track_count=25,
    )


def _track(
    track_id: str,
    title: str,
    artist: str,
    *,
    genre: str = "",
) -> TrackCandidate:
    return TrackCandidate(id=track_id, title=title, artists=[artist], genre=genre)


def _ranked(
    items: list[tuple[TrackCandidate, float]],
) -> list[tuple[TrackCandidate, float]]:
    return sorted(items, key=lambda item: item[1], reverse=True)


def _clean_and_select(
    profile: MusicProfile,
    ranked: list[tuple[TrackCandidate, float]],
) -> tuple[list[tuple[TrackCandidate, float]], list[TrackCandidate]]:
    clean = [(track, score) for track, score in ranked if not is_spurious_track(track, profile)]
    filtered_out = [track for track, _ in ranked if is_spurious_track(track, profile)]
    selected = select_playlist_tracks(clean, profile)
    return selected, filtered_out


def _kitchen_pool() -> list[tuple[TrackCandidate, float]]:
    good = [
        (_track("k1", "Withered", "Parcels", genre="indie pop"), 0.94),
        (_track("k2", "White Gloves", "Khruangbin", genre="funk"), 0.93),
        (_track("k3", "Show Me How", "Men I Trust", genre="indie pop"), 0.92),
        (_track("k4", "Sugar", "Camyo", genre="chill"), 0.91),
        (_track("k5", "Big Jet Plane", "Angus & Julia Stone", genre="indie"), 0.90),
        (_track("k6", "Midnight", "Soulive", genre="funk"), 0.88),
        (_track("k7", "Power", "Pompeya", genre="indie pop"), 0.87),
        (_track("k8", "Rose", "Toro y Moi", genre="chill"), 0.86),
        (_track("k9", "Multi-Love", "Unknown Mortal Orchestra", genre="indie"), 0.85),
        (_track("k10", "Seahorse", "Ducktails", genre="indie"), 0.84),
    ]
    fillers = [
        (
            _track(f"kf{i}", f"Sunday Morning {i}", f"Real Band {i}", genre="indie pop"),
            0.83 - i * 0.005,
        )
        for i in range(20)
    ]
    junk = [
        (
            _track(
                "kj1",
                "Inspired Saxophone Bossa Nova - Vibe for Cooking",
                "Music for Cooking Moods",
            ),
            0.99,
        ),
        (_track("kj2", "Indie Pop", "Playlist Universe"), 0.98),
        (_track("kj3", "Vlone", "Hauvy"), 0.70),
    ]
    return _ranked(good + fillers + junk)


def _coding_pool() -> list[tuple[TrackCandidate, float]]:
    good = [
        (_track("c1", "A Walk", "Tycho", genre="ambient"), 0.95),
        (_track("c2", "Feather", "Nujabes", genre="lo-fi"), 0.94),
        (_track("c3", "Kiara", "Bonobo", genre="downtempo"), 0.93),
        (_track("c4", "Nothing It Can", "Helios", genre="ambient"), 0.92),
        (_track("c5", "Weightless", "Marconi Union", genre="ambient"), 0.90),
        (_track("c6", "Daydreaming", "Radiohead", genre="electronic"), 0.86),
        (_track("c7", "Holocene", "Bon Iver", genre="indie"), 0.84),
    ]
    fillers = [
        (
            _track(f"cf{i}", f"Soft Horizon {i}", f"North Signal {i}", genre="ambient"),
            0.83 - i * 0.004,
        )
        for i in range(22)
    ]
    junk = [
        (_track("cj1", "Coding Music for Programming", "Study Beats Playlist"), 0.99),
        (_track("cj2", "Lo-fi Beats - Music for Focus", "Focus Music Moods"), 0.98),
        (_track("cj3", "Tycho", "Cover Band All-Stars"), 0.80),
    ]
    return _ranked(good + fillers + junk)


def _synthwave_pool() -> list[tuple[TrackCandidate, float]]:
    good = [
        (_track("s1", "Nightcall", "Kavinsky", genre="synthwave"), 0.96),
        (_track("s2", "Future Club", "Perturbator", genre="synthwave"), 0.95),
        (_track("s3", "Tech Noir", "Gunship", genre="synthwave"), 0.94),
        (_track("s4", "On the Run", "Timecop1983", genre="retrowave"), 0.93),
        (_track("s5", "Le Perv", "Carpenter Brut", genre="synthwave"), 0.91),
        (_track("s6", "A.M.", "The Midnight", genre="synthwave"), 0.89),
        (_track("s7", "Near Light", "FM-84", genre="retrowave"), 0.88),
    ]
    fillers = [
        (
            _track(f"sf{i}", f"Chrome Highway {i}", f"Neon Pilot {i}", genre="synthwave"),
            0.87 - i * 0.004,
        )
        for i in range(22)
    ]
    junk = [
        (_track("sj1", "Synthwave Night - Vibe for Driving", "Music for Night Drive"), 0.99),
        (_track("sj2", "Nightcall (Kavinsky Cover)", "Barcelona 82"), 0.97),
        (_track("sj3", "Kavinsky", "Eewas Cesium"), 0.85),
    ]
    return _ranked(good + fillers + junk)


def test_golden_prompt_constants_match_frontend_samples() -> None:
    assert GOLDEN_PROMPTS["kitchen"] == "под настроение пока варю макароны"
    assert "кодинг" in GOLDEN_PROMPTS["coding"]
    assert "синтвейв" in GOLDEN_PROMPTS["synthwave"]


def test_golden_search_queries_are_not_generic_seo() -> None:
    for profile in (_kitchen_profile(), _coding_profile(), _synthwave_profile()):
        for query in profile.search_queries:
            assert not is_generic_search_query(query), query


def test_golden_kitchen_snapshot() -> None:
    profile = _kitchen_profile()
    selected, filtered = _clean_and_select(profile, _kitchen_pool())

    assert {track.id for track in filtered} >= {"kj1", "kj2"}
    assert len(selected) == 25
    assert {track.id for track, _ in selected[:5]} == {"k1", "k2", "k3", "k4", "k5"}
    top_artists = {track.artists[0] for track, _ in selected[:5]}
    assert top_artists >= {"Parcels", "Khruangbin", "Men I Trust", "Camyo"}
    assert all(track.id not in {"kj1", "kj2"} for track, _ in selected)
    assert [round(score, 3) for _, score in selected[:5]] == [0.94, 0.93, 0.92, 0.91, 0.90]


def test_golden_coding_snapshot() -> None:
    profile = _coding_profile()
    selected, filtered = _clean_and_select(profile, _coding_pool())

    assert {track.id for track in filtered} >= {"cj1", "cj2", "cj3"}
    assert len(selected) == 25
    assert [track.id for track, _ in selected[:4]] == ["c1", "c2", "c3", "c4"]
    top_artists = {track.artists[0] for track, _ in selected[:4]}
    assert top_artists == {"Tycho", "Nujabes", "Bonobo", "Helios"}
    assert all(track.id not in {"cj1", "cj2", "cj3"} for track, _ in selected)
    assert [round(score, 3) for _, score in selected[:4]] == [0.95, 0.94, 0.93, 0.92]


def test_golden_synthwave_snapshot() -> None:
    profile = _synthwave_profile()
    selected, filtered = _clean_and_select(profile, _synthwave_pool())

    assert {track.id for track in filtered} >= {"sj1", "sj2", "sj3"}
    assert len(selected) == 25
    assert [track.id for track, _ in selected[:4]] == ["s1", "s2", "s3", "s4"]
    top_artists = {track.artists[0] for track, _ in selected[:4]}
    assert top_artists == {"Kavinsky", "Perturbator", "Gunship", "Timecop1983"}
    assert all(track.id not in {"sj1", "sj2", "sj3"} for track, _ in selected)
    assert [round(score, 3) for _, score in selected[:4]] == [0.96, 0.95, 0.94, 0.93]
