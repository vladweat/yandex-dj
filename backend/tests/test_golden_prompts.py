"""Golden smoke: 7 situational prompts — mock scores, без LLM/Yandex.

Golden fixtures cover representative prompts; keep SAMPLE_PROMPTS in frontend in sync.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate
from app.utils.quality import is_spurious_track
from app.utils.scoring import select_playlist_tracks
from app.utils.search_queries import is_rejected_search_query

GOLDEN_PROMPTS = {
    "kitchen": "под настроение пока варю макароны",
    "coding": "спокойная музыка для кодинга поздней ночью",
    "synthwave": "саундтрек для ночной поездки в стиле синтвейв",
    "workout": "энергичная музыка для пробежки",
    "sleep": "тихая музыка чтобы уснуть",
    "party": "танцевальный плейлист для вечеринки дома",
    "rain": "грустная музыка под дождь у окна",
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
            "Khruangbin",
            "Men I Trust",
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


def _workout_profile() -> MusicProfile:
    return MusicProfile(
        playlist_title="Темп пробежки",
        playlist_description="Энергичный электропоп и инди для бега",
        primary_genres=["electro pop", "indie dance", "alt rock"],
        mood_tags=["energetic", "uplifting", "driving"],
        vocal_type="any",
        reference_artists=["The Chemical Brothers", "Justice", "LCD Soundsystem", "Peggy Gou"],
        search_queries=[
            "Chemical Brothers",
            "Justice electro",
            "Peggy Gou dance",
        ],
        target_track_count=25,
    )


def _sleep_profile() -> MusicProfile:
    return MusicProfile(
        playlist_title="Тихий сон",
        playlist_description="Мягкий эмбиент без резких пиков",
        primary_genres=["ambient", "drone", "neo-classical"],
        mood_tags=["calm", "soft", "sleepy", "quiet"],
        vocal_type="instrumental_only",
        reference_artists=["Brian Eno", "Max Richter", "Ólafur Arnalds", "Hammock"],
        search_queries=[
            "Brian Eno ambient",
            "Max Richter neo classical",
            "Ólafur Arnalds piano",
        ],
        target_track_count=25,
    )


def _party_profile() -> MusicProfile:
    return MusicProfile(
        playlist_title="Домашняя вечеринка",
        playlist_description="Танцевальный хаус и диско для гостиной",
        primary_genres=["house", "disco", "funk"],
        mood_tags=["festive", "upbeat", "danceable"],
        vocal_type="any",
        reference_artists=["Daft Punk", "Disclosure", "Purple Disco Machine", "Todd Terje"],
        search_queries=[
            "Daft Punk house disco",
            "Disclosure dance",
            "Purple Disco Machine funky",
        ],
        target_track_count=25,
    )


def _rain_profile() -> MusicProfile:
    return MusicProfile(
        playlist_title="Дождь у окна",
        playlist_description="Меланхоличный инди и slowcore под дождь",
        primary_genres=["indie folk", "slowcore", "dream pop"],
        mood_tags=["melancholy", "rainy", "introspective"],
        vocal_type="any",
        reference_artists=["Radiohead", "The National", "Phoebe Bridgers", "Slowdive"],
        search_queries=[
            "Radiohead",
            "The National indie",
            "Phoebe Bridgers indie folk",
        ],
        target_track_count=25,
    )


_PROFILES = {
    "kitchen": _kitchen_profile,
    "coding": _coding_profile,
    "synthwave": _synthwave_profile,
    "workout": _workout_profile,
    "sleep": _sleep_profile,
    "party": _party_profile,
    "rain": _rain_profile,
}


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


def _filler_pool(
    prefix: str,
    genre: str,
    *,
    count: int = 22,
    start_score: float = 0.83,
    step: float = 0.004,
) -> list[tuple[TrackCandidate, float]]:
    return [
        (
            _track(f"{prefix}{i}", f"Fill Track {i}", f"Fill Artist {i}", genre=genre),
            start_score - i * step,
        )
        for i in range(count)
    ]


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


def _workout_pool() -> list[tuple[TrackCandidate, float]]:
    good = [
        (_track("w1", "Galvanize", "The Chemical Brothers", genre="electro"), 0.96),
        (_track("w2", "D.A.N.C.E.", "Justice", genre="electro"), 0.95),
        (_track("w3", "Dance Yrself Clean", "LCD Soundsystem", genre="indie dance"), 0.94),
        (_track("w4", "It Goes Like", "Peggy Gou", genre="house"), 0.93),
        (_track("w5", "Block Rockin' Beats", "The Chemical Brothers", genre="electro"), 0.90),
        (_track("w6", "Genesis", "Justice", genre="electro"), 0.88),
    ]
    junk = [
        (_track("wj1", "Workout Motivation Music - Vibe for Running", "Gym Beats Moods"), 0.99),
        (_track("wj2", "Electro Pop", "Playlist Universe"), 0.98),
        (_track("wj3", "The Chemical Brothers", "Cover Band All-Stars"), 0.80),
    ]
    return _ranked(good + _filler_pool("wf", "electro", start_score=0.87) + junk)


def _sleep_pool() -> list[tuple[TrackCandidate, float]]:
    good = [
        (_track("sl1", "1/1", "Brian Eno", genre="ambient"), 0.96),
        (_track("sl2", "On the Nature of Daylight", "Max Richter", genre="neo-classical"), 0.95),
        (_track("sl3", "Saman", "Ólafur Arnalds", genre="neo-classical"), 0.94),
        (_track("sl4", "Turn Away", "Hammock", genre="ambient"), 0.93),
        (_track("sl5", "An Ending (Ascent)", "Brian Eno", genre="ambient"), 0.90),
        (_track("sl6", "Path 5", "Max Richter", genre="neo-classical"), 0.88),
    ]
    junk = [
        (_track("slj1", "Sleep Music for Deep Rest - Vibe for Sleeping", "Sleep Moods"), 0.99),
        (_track("slj2", "Ambient", "Playlist Universe"), 0.98),
        (_track("slj3", "Brian Eno", "Cover Band All-Stars"), 0.80),
    ]
    return _ranked(good + _filler_pool("slf", "ambient", start_score=0.87) + junk)


def _party_pool() -> list[tuple[TrackCandidate, float]]:
    good = [
        (_track("p1", "One More Time", "Daft Punk", genre="house"), 0.96),
        (_track("p2", "Latch", "Disclosure", genre="house"), 0.95),
        (_track("p3", "Hypnotized", "Purple Disco Machine", genre="disco"), 0.94),
        (_track("p4", "Inspector Norse", "Todd Terje", genre="disco"), 0.93),
        (_track("p5", "Around the World", "Daft Punk", genre="house"), 0.90),
        (_track("p6", "You & Me", "Disclosure", genre="house"), 0.88),
    ]
    junk = [
        (_track("pj1", "Party Hits - Vibe for Dancing", "Club Moods Playlist"), 0.99),
        (_track("pj2", "House", "Playlist Universe"), 0.98),
        (_track("pj3", "Daft Punk", "Cover Band All-Stars"), 0.80),
    ]
    return _ranked(good + _filler_pool("pf", "house", start_score=0.87) + junk)


def _rain_pool() -> list[tuple[TrackCandidate, float]]:
    good = [
        (_track("r1", "How to Disappear Completely", "Radiohead", genre="alt"), 0.96),
        (_track("r2", "Fake Empire", "The National", genre="indie"), 0.95),
        (_track("r3", "Motion Sickness", "Phoebe Bridgers", genre="indie folk"), 0.94),
        (_track("r4", "When the Sun Hits", "Slowdive", genre="dream pop"), 0.93),
        (_track("r5", "Karma Police", "Radiohead", genre="alt"), 0.90),
        (_track("r6", "Bloodbuzz Ohio", "The National", genre="indie"), 0.88),
    ]
    junk = [
        (_track("rj1", "Sad Rainy Day Songs - Vibe for Crying", "Rain Moods"), 0.99),
        (_track("rj2", "Indie Folk", "Playlist Universe"), 0.98),
        (_track("rj3", "Radiohead", "Cover Band All-Stars"), 0.80),
    ]
    return _ranked(good + _filler_pool("rf", "indie", start_score=0.87) + junk)


_POOLS = {
    "kitchen": _kitchen_pool,
    "coding": _coding_pool,
    "synthwave": _synthwave_pool,
    "workout": _workout_pool,
    "sleep": _sleep_pool,
    "party": _party_pool,
    "rain": _rain_pool,
}

_EXPECTED_TOP = {
    "kitchen": {
        "top_ids": {"k1", "k2", "k3", "k4", "k5"},
        "top_artists": {"Parcels", "Khruangbin", "Men I Trust", "Camyo"},
        "junk_ids": {"kj1", "kj2", "kj3"},
        "filtered_min": {"kj1", "kj2"},
        "top_scores": [0.94, 0.93, 0.92, 0.91, 0.90],
        "ordered_ids": None,
    },
    "coding": {
        "top_ids": None,
        "top_artists": {"Tycho", "Nujabes", "Bonobo", "Helios"},
        "junk_ids": {"cj1", "cj2", "cj3"},
        "filtered_min": {"cj1", "cj2", "cj3"},
        "top_scores": [0.95, 0.94, 0.93, 0.92],
        "ordered_ids": ["c1", "c2", "c3", "c4"],
    },
    "synthwave": {
        "top_ids": None,
        "top_artists": {"Kavinsky", "Perturbator", "Gunship", "Timecop1983"},
        "junk_ids": {"sj1", "sj2", "sj3"},
        "filtered_min": {"sj1", "sj2", "sj3"},
        "top_scores": [0.96, 0.95, 0.94, 0.93],
        "ordered_ids": ["s1", "s2", "s3", "s4"],
    },
    "workout": {
        "top_ids": None,
        "top_artists": {"The Chemical Brothers", "Justice", "LCD Soundsystem", "Peggy Gou"},
        "junk_ids": {"wj1", "wj2", "wj3"},
        "filtered_min": {"wj1", "wj2", "wj3"},
        "top_scores": [0.96, 0.95, 0.94, 0.93],
        "ordered_ids": ["w1", "w2", "w3", "w4"],
    },
    "sleep": {
        "top_ids": None,
        "top_artists": {"Brian Eno", "Max Richter", "Ólafur Arnalds", "Hammock"},
        "junk_ids": {"slj1", "slj2", "slj3"},
        "filtered_min": {"slj1", "slj2", "slj3"},
        "top_scores": [0.96, 0.95, 0.94, 0.93],
        "ordered_ids": ["sl1", "sl2", "sl3", "sl4"],
    },
    "party": {
        "top_ids": None,
        "top_artists": {"Daft Punk", "Disclosure", "Purple Disco Machine", "Todd Terje"},
        "junk_ids": {"pj1", "pj2", "pj3"},
        "filtered_min": {"pj1", "pj2", "pj3"},
        "top_scores": [0.96, 0.95, 0.94, 0.93],
        "ordered_ids": ["p1", "p2", "p3", "p4"],
    },
    "rain": {
        "top_ids": None,
        "top_artists": {"Radiohead", "The National", "Phoebe Bridgers", "Slowdive"},
        "junk_ids": {"rj1", "rj2", "rj3"},
        "filtered_min": {"rj1", "rj2", "rj3"},
        "top_scores": [0.96, 0.95, 0.94, 0.93],
        "ordered_ids": ["r1", "r2", "r3", "r4"],
    },
}


def test_golden_prompt_count_in_range() -> None:
    assert 5 <= len(GOLDEN_PROMPTS) <= 10


def test_golden_prompt_constants_match_frontend_samples() -> None:
    frontend = Path(__file__).resolve().parents[2] / (
        "frontend/src/features/playlist/playlist-form-utils.ts"
    )
    text = frontend.read_text(encoding="utf-8")
    match = re.search(r"export const SAMPLE_PROMPTS = \[([\s\S]*?)\] as const", text)
    assert match is not None, "SAMPLE_PROMPTS not found in frontend"
    samples = re.findall(r'"([^"]+)"', match.group(1))
    assert samples == list(GOLDEN_PROMPTS.values())


def test_golden_search_queries_are_not_rejected() -> None:
    for key, factory in _PROFILES.items():
        profile = factory()
        for query in profile.search_queries:
            assert not is_rejected_search_query(query), f"{key}: {query}"


def _assert_golden_snapshot(key: str) -> None:
    profile = _PROFILES[key]()
    selected, filtered = _clean_and_select(profile, _POOLS[key]())
    expect = _EXPECTED_TOP[key]

    assert {track.id for track in filtered} >= expect["filtered_min"]
    assert len(selected) == 25
    if expect["ordered_ids"] is not None:
        n = len(expect["ordered_ids"])
        assert [track.id for track, _ in selected[:n]] == expect["ordered_ids"]
        top_artists = {track.artists[0] for track, _ in selected[:n]}
        assert top_artists == expect["top_artists"]
        assert [round(score, 3) for _, score in selected[:n]] == expect["top_scores"]
    else:
        assert {track.id for track, _ in selected[:5]} == expect["top_ids"]
        top_artists = {track.artists[0] for track, _ in selected[:5]}
        assert top_artists >= expect["top_artists"]
        assert [round(score, 3) for _, score in selected[:5]] == expect["top_scores"]
    assert all(track.id not in expect["junk_ids"] for track, _ in selected)


def test_golden_kitchen_snapshot() -> None:
    _assert_golden_snapshot("kitchen")


def test_golden_coding_snapshot() -> None:
    _assert_golden_snapshot("coding")


def test_golden_synthwave_snapshot() -> None:
    _assert_golden_snapshot("synthwave")


def test_golden_workout_snapshot() -> None:
    _assert_golden_snapshot("workout")


def test_golden_sleep_snapshot() -> None:
    _assert_golden_snapshot("sleep")


def test_golden_party_snapshot() -> None:
    _assert_golden_snapshot("party")


def test_golden_rain_snapshot() -> None:
    _assert_golden_snapshot("rain")
