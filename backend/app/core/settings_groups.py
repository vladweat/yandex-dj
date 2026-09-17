"""Группы настроек пайплайна (read-only view поверх плоских env-полей)."""

from pydantic import BaseModel


class RetrievalSettings(BaseModel):
    max_candidates: int
    min_candidates_pool: int
    target_candidates_pool: int
    artist_tracks_limit: int
    search_tracks_per_query: int
    search_pages: int
    search_expand_max_queries: int
    retrieval_expand_passes: int
    min_clean_candidates: int
    similar_seeds_per_artist: int
    max_similar_requests: int
    reference_artists_tops_limit: int
    discovered_artists_limit: int
    discovered_similar_seeds: int
    feedback_artists_limit: int
    feedback_similar_seeds: int


class LibrarySettings(BaseModel):
    artist_limit: int
    seed_artists: int
    similar_seeds: int
    likes_track_limit: int
    recent_full_models: int
    artist_boost: float


class ScoringSettings(BaseModel):
    embed_limit: int
    batch_size: int
    torch_threads: int
    max_tracks_per_artist: int


class YandexSettings(BaseModel):
    rate_limit_delay_sec: float
    api_max_retries: int
    device_flow_timeout_sec: int
