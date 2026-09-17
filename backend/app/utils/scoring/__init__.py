"""Скоринг: cosine similarity → adaptive cutoff → diversity → playlist select."""

from app.utils.scoring.adjustments import (
    apply_library_artist_boost,
    apply_mood_title_demote,
    apply_reference_anchor_boost,
    is_score_plateau,
    prefer_non_anchors_on_plateau,
)
from app.utils.scoring.diversity import (
    apply_diversity_filter,
    max_anchor_tracks,
    max_tracks_per_artist,
)
from app.utils.scoring.embedding import (
    build_prompt_text,
    candidates_for_embedding,
    cosine_scores,
    fallback_scores,
    merge_embedding_rank,
)
from app.utils.scoring.floors import adaptive_score_floor, filter_by_top_median_gap
from app.utils.scoring.selection import (
    PlaylistSelection,
    select_playlist_tracks,
    select_playlist_with_meta,
)

__all__ = [
    "PlaylistSelection",
    "adaptive_score_floor",
    "apply_diversity_filter",
    "apply_library_artist_boost",
    "apply_mood_title_demote",
    "apply_reference_anchor_boost",
    "build_prompt_text",
    "candidates_for_embedding",
    "cosine_scores",
    "fallback_scores",
    "filter_by_top_median_gap",
    "is_score_plateau",
    "max_anchor_tracks",
    "max_tracks_per_artist",
    "merge_embedding_rank",
    "prefer_non_anchors_on_plateau",
    "select_playlist_tracks",
    "select_playlist_with_meta",
]
