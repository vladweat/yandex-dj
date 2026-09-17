"""Embedding query, cosine similarity, fallback ranking."""

from __future__ import annotations

import numpy as np
from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate
from app.utils.quality import artist_matches_reference, artist_tokens, hard_references_in_artists
from app.utils.scoring.adjustments import apply_reference_anchor_boost


def build_prompt_text(profile: MusicProfile, user_prompt: str | None = None) -> str:
    parts: list[str] = []
    if user_prompt and user_prompt.strip():
        parts.append(user_prompt.strip())
    parts.append(profile.playlist_description)
    if profile.primary_genres:
        parts.append("Жанры: " + ", ".join(profile.primary_genres))
    if profile.mood_tags:
        parts.append("Настроение: " + ", ".join(profile.mood_tags))
    # reference_artists — только retrieval, не embedding («карю макароны» без имён).
    if profile.vocal_type != "any":
        parts.append(f"Вокал: {profile.vocal_type}")
    return ". ".join(parts)


def cosine_scores(query_vec: np.ndarray, doc_vecs: np.ndarray) -> np.ndarray:
    if doc_vecs.size == 0:
        return np.array([], dtype=np.float64)
    query = query_vec.astype(np.float64)
    docs = doc_vecs.astype(np.float64)
    query_norm = np.linalg.norm(query)
    doc_norms = np.linalg.norm(docs, axis=1)
    if query_norm == 0:
        return np.zeros(len(docs), dtype=np.float64)
    safe_norms = np.where(doc_norms == 0, 1.0, doc_norms)
    return (docs @ query) / (query_norm * safe_norms)


def candidates_for_embedding(
    candidates: list[TrackCandidate],
    *,
    limit: int,
) -> list[TrackCandidate]:
    """Весь пул кандидатов в embedding; limit<=0 — без обрезки."""
    if limit <= 0 or len(candidates) <= limit:
        return candidates
    return candidates[:limit]


def fallback_scores(
    profile: MusicProfile,
    candidates: list[TrackCandidate],
) -> list[tuple[TrackCandidate, float]]:
    genres = {genre.lower() for genre in profile.primary_genres}
    ref_artists = {artist.lower() for artist in profile.reference_artists}
    pool_size = max(len(candidates), 1)

    scored: list[tuple[TrackCandidate, float]] = []
    for index, track in enumerate(candidates):
        score = 0.0
        track_genre = track.genre.lower()
        if track_genre and any(genre in track_genre or track_genre in genre for genre in genres):
            score += 1.0
        artists = artist_tokens(track)
        if any(artist_matches_reference(artist, ref) for artist in artists for ref in ref_artists):
            score += 0.5
        if hard_references_in_artists(track, profile):
            score += 0.15
        score += 0.01 * (pool_size - index) / pool_size
        scored.append((track, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


def merge_embedding_rank(
    profile: MusicProfile,
    candidates: list[TrackCandidate],
    embedded: list[tuple[TrackCandidate, float]],
) -> list[tuple[TrackCandidate, float]]:
    if not embedded:
        return fallback_scores(profile, candidates)
    return apply_reference_anchor_boost(embedded, profile)
