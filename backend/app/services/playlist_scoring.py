"""Scoring + feedback expand для пайплайна generate."""

from __future__ import annotations

from app.core.config import settings
from app.schemas.llm import MusicProfile
from app.schemas.playlist import DiversityMode
from app.schemas.scoring import ScoredTrack
from app.schemas.track import TrackCandidate
from app.services.retrieval_service import RetrievalService, non_anchor_artists_from_ranked
from app.services.scoring_service import ScoringService
from app.utils.playlist_filters import (
    apply_candidate_pool_filters,
    apply_selected_track_filters,
)
from app.utils.quality import artist_matches_reference
from app.utils.scoring import apply_library_artist_boost


def _boost_and_select(
    ranked_pool: list[tuple[TrackCandidate, float]],
    profile: MusicProfile,
    *,
    scoring: ScoringService,
    diversity: DiversityMode,
    library: list[str],
    excludes: list[str],
    languages: list[str],
) -> tuple[list[ScoredTrack], bool]:
    pool = ranked_pool
    if library:
        pool = apply_library_artist_boost(
            pool,
            library,
            boost=settings.library.artist_boost,
        )
    selected, shortfall = scoring.select(
        pool,
        profile,
        diversity=diversity,
    )
    return apply_selected_track_filters(
        selected,
        exclude_artists=excludes,
        exclude_languages=languages,
    ), shortfall


async def score_with_feedback(
    profile: MusicProfile,
    candidates: list[TrackCandidate],
    *,
    prompt: str,
    access_token: str,
    excludes: list[str],
    diversity: DiversityMode,
    scoring: ScoringService,
    retrieval: RetrievalService,
    library_artists: list[str] | None = None,
    exclude_languages: list[str] | None = None,
) -> tuple[list[ScoredTrack], list[TrackCandidate], str, bool]:
    library = library_artists or []
    languages = list(exclude_languages or [])
    ranked_pool, method = await scoring.rank_pool(
        profile,
        candidates,
        user_prompt=prompt,
    )
    selected, shortfall = _boost_and_select(
        ranked_pool,
        profile,
        scoring=scoring,
        diversity=diversity,
        library=library,
        excludes=excludes,
        languages=languages,
    )

    if len(selected) >= profile.target_track_count:
        return (
            selected[: profile.target_track_count],
            candidates,
            method,
            shortfall,
        )

    feedback_artists = non_anchor_artists_from_ranked(
        ranked_pool,
        profile,
        limit=settings.retrieval.feedback_artists_limit,
    )
    feedback_artists = [
        artist
        for artist in feedback_artists
        if not any(artist_matches_reference(artist, excluded) for excluded in excludes)
    ]
    if not feedback_artists:
        return selected, candidates, method, shortfall

    known_ids = {track.id for track, _ in ranked_pool}
    candidates = await retrieval.expand_from_artists(
        profile,
        access_token,
        candidates,
        feedback_artists,
        similar_seeds=settings.retrieval.feedback_similar_seeds,
    )
    candidates = apply_candidate_pool_filters(
        candidates,
        exclude_artists=excludes,
        exclude_languages=languages,
    )
    new_candidates = [track for track in candidates if track.id not in known_ids]
    if not new_candidates:
        return selected, candidates, method, shortfall

    ranked_pool, method = await scoring.rank_pool_merge(
        profile,
        ranked_pool,
        new_candidates,
        user_prompt=prompt,
    )
    selected, shortfall = _boost_and_select(
        ranked_pool,
        profile,
        scoring=scoring,
        diversity=diversity,
        library=library,
        excludes=excludes,
        languages=languages,
    )
    return (
        selected[: profile.target_track_count],
        candidates,
        method,
        shortfall,
    )
