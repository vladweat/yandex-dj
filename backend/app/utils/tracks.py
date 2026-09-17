"""Нормализация и конвертация треков из yandex-music."""

from app.schemas.track import TrackCandidate
from yandex_music import Track


def track_to_candidate(track: Track) -> TrackCandidate | None:
    if track.id is None:
        return None

    artists = [a.name for a in (track.artists or []) if a and a.name]
    album = ""
    genre = ""
    if track.albums:
        first_album = track.albums[0]
        album = first_album.title or ""
        genre = first_album.genre or ""

    return TrackCandidate(
        id=str(track.id),
        title=track.title or "",
        artists=artists,
        album=album,
        genre=genre,
        version=track.version or "",
        duration_ms=track.duration_ms or 0,
        available=track.available if track.available is not None else True,
    )


def tracks_to_candidates(tracks: list[Track]) -> list[TrackCandidate]:
    result: list[TrackCandidate] = []
    for track in tracks:
        candidate = track_to_candidate(track)
        if candidate is not None:
            result.append(candidate)
    return result


def normalize_pool(tracks: list[TrackCandidate]) -> list[TrackCandidate]:
    """Дедупликация и фильтр unavailable (ТЗ §4.3)."""
    seen_ids: set[str] = set()
    seen_titles: set[str] = set()
    id_index: dict[str, int] = {}
    result: list[TrackCandidate] = []

    for track in tracks:
        if not track.available:
            continue
        key = track.artist_title_key
        if track.id in seen_ids:
            index = id_index[track.id]
            if track.retrieval_tier > result[index].retrieval_tier:
                result[index] = track
            continue
        if key in seen_titles:
            continue
        seen_ids.add(track.id)
        seen_titles.add(key)
        id_index[track.id] = len(result)
        result.append(track)

    return result


def with_retrieval_tier(
    tracks: list[TrackCandidate],
    tier: int,
) -> list[TrackCandidate]:
    """Пометить треки источником; при merge в normalize_pool сохранится max tier."""
    return [
        track if track.retrieval_tier >= tier else track.model_copy(update={"retrieval_tier": tier})
        for track in tracks
    ]
