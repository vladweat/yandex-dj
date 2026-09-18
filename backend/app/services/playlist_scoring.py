"""Scoring + feedback expand для пайплайна generate."""

from __future__ import annotations

from app.core.config import settings
from app.schemas.llm import MusicProfile
from app.schemas.playlist import DiversityMode
from app.schemas.scoring import ScoredTrack
from app.schemas.track import TrackCandidate
from app.services.lyrics_filter import (
    instrumental_lyrics_filter_needed,
    prepare_instrumental_ranked_pool,
    refine_instrumental_selection,
)
from app.services.retrieval_service import RetrievalService, non_anchor_artists_from_ranked
from app.services.scoring_service import ScoringService
from app.services.track_cache import TrackCacheService
from app.services.yandex_music_service import YandexMusicService
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
    exclude_explicit: bool = False,
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
        exclude_explicit=exclude_explicit,
    ), shortfall


async def _instrumental_lyrics_prepare_and_select(
    *,
    yandex: YandexMusicService,
    track_cache: TrackCacheService,
    access_token: str,
    profile: MusicProfile,
    ranked_pool: list[tuple[TrackCandidate, float]],
    scoring: ScoringService,
    diversity: DiversityMode,
    library: list[str],
    excludes: list[str],
    languages: list[str],
    exclude_explicit: bool,
) -> tuple[list[tuple[TrackCandidate, float]], list[ScoredTrack], bool, list[str], dict[str, bool]]:
    lyrics_warnings: list[str] = []
    has_lyrics: dict[str, bool] = {}
    client = await yandex.init_client(access_token)
    ranked_pool, has_lyrics, prep_warnings = await prepare_instrumental_ranked_pool(
        yandex=yandex,
        cache=track_cache,
        client=client,
        profile=profile,
        ranked=ranked_pool,
    )
    lyrics_warnings.extend(prep_warnings)

    selected, shortfall = _boost_and_select(
        ranked_pool,
        profile,
        scoring=scoring,
        diversity=diversity,
        library=library,
        excludes=excludes,
        languages=languages,
        exclude_explicit=exclude_explicit,
    )
    selected, refine_warnings = refine_instrumental_selection(
        selected,
        ranked_pool,
        has_lyrics,
    )
    lyrics_warnings.extend(refine_warnings)
    return ranked_pool, selected, shortfall, lyrics_warnings, has_lyrics


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
    exclude_explicit: bool = False,
    yandex: YandexMusicService | None = None,
    track_cache: TrackCacheService | None = None,
) -> tuple[list[ScoredTrack], list[TrackCandidate], str, bool, list[str]]:
    library = library_artists or []
    languages = list(exclude_languages or [])
    lyrics_warnings: list[str] = []
    use_lyrics = (
        instrumental_lyrics_filter_needed(profile)
        and yandex is not None
        and track_cache is not None
    )

    ranked_pool, method = await scoring.rank_pool(
        profile,
        candidates,
        user_prompt=prompt,
    )

    if use_lyrics:
        ranked_pool, selected, shortfall, lyrics_warnings, has_lyrics = (
            await _instrumental_lyrics_prepare_and_select(
                yandex=yandex,
                track_cache=track_cache,
                access_token=access_token,
                profile=profile,
                ranked_pool=ranked_pool,
                scoring=scoring,
                diversity=diversity,
                library=library,
                excludes=excludes,
                languages=languages,
                exclude_explicit=exclude_explicit,
            )
        )
    else:
        has_lyrics = {}
        selected, shortfall = _boost_and_select(
            ranked_pool,
            profile,
            scoring=scoring,
            diversity=diversity,
            library=library,
            excludes=excludes,
            languages=languages,
            exclude_explicit=exclude_explicit,
        )

    if len(selected) >= profile.target_track_count:
        return (
            selected[: profile.target_track_count],
            candidates,
            method,
            shortfall,
            lyrics_warnings,
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
        return selected, candidates, method, shortfall, lyrics_warnings

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
        exclude_explicit=exclude_explicit,
    )
    new_candidates = [track for track in candidates if track.id not in known_ids]
    if not new_candidates:
        return selected, candidates, method, shortfall, lyrics_warnings

    ranked_pool, method = await scoring.rank_pool_merge(
        profile,
        ranked_pool,
        new_candidates,
        user_prompt=prompt,
    )

    if use_lyrics and has_lyrics:
        client = await yandex.init_client(access_token)
        ranked_pool, extra_map, prep_warnings = await prepare_instrumental_ranked_pool(
            yandex=yandex,
            cache=track_cache,
            client=client,
            profile=profile,
            ranked=ranked_pool,
        )
        has_lyrics = {**has_lyrics, **extra_map}
        lyrics_warnings.extend(prep_warnings)

    selected, shortfall = _boost_and_select(
        ranked_pool,
        profile,
        scoring=scoring,
        diversity=diversity,
        library=library,
        excludes=excludes,
        languages=languages,
        exclude_explicit=exclude_explicit,
    )
    if use_lyrics:
        selected, refine_warnings = refine_instrumental_selection(
            selected,
            ranked_pool,
            has_lyrics,
        )
        lyrics_warnings.extend(refine_warnings)

    return (
        selected[: profile.target_track_count],
        candidates,
        method,
        shortfall,
        lyrics_warnings,
    )
