from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.settings_groups import (
    LibrarySettings,
    RetrievalSettings,
    ScoringSettings,
    YandexSettings,
)

DEFAULT_CORS_ORIGINS = (
    "http://localhost:3001,http://127.0.0.1:3001,http://localhost:3000,http://127.0.0.1:3000"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://prompt_dj:prompt_dj@localhost/prompt_dj"
    database_connect_timeout_sec: int = 5
    redis_url: str = "redis://localhost:6379/0"
    token_encryption_key: str = ""

    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = ""
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "intfloat/multilingual-e5-base"
    embedding_model_path: str = ""  # /opt/models в Docker (offline)

    max_candidates: int = 300
    min_candidates_pool: int = 100
    target_candidates_pool: int = 150
    max_tracks_per_artist: int = 2
    pipeline_timeout_sec: int = 90
    # Soft freemium: new generations/day (source_id IS NULL). 0 = unlimited.
    daily_generation_limit: int = 10
    track_cache_ttl_sec: int = 86400
    artist_tracks_limit: int = 20
    search_tracks_per_query: int = 50
    search_pages: int = 2
    search_expand_max_queries: int = 12
    retrieval_expand_passes: int = 4
    min_clean_candidates: int = 50
    similar_seeds_per_artist: int = 3
    max_similar_requests: int = 12
    # Сколько reference_artists тянуть топами (остальные — только search/discovered).
    reference_artists_tops_limit: int = 5
    # Не-якорные артисты из clean-пула → их топы + similar (ширина пула)
    discovered_artists_limit: int = 12
    discovered_similar_seeds: int = 8
    # После первого scoring — добор по лучшим не-якорным
    feedback_artists_limit: int = 8
    feedback_similar_seeds: int = 8
    # Soft bias из likes / recently played (use_library)
    library_artist_limit: int = 24
    library_seed_artists: int = 8
    library_similar_seeds: int = 6
    library_likes_track_limit: int = 80
    library_recent_full_models: int = 40
    library_artist_boost: float = 0.025
    # Soft lyrics filter (instrumental_only): tracks_lyrics API, не default hot path
    lyrics_check_limit: int = 80
    lyrics_vocal_score_penalty: float = 0.045
    # 0 = embed весь пул кандидатов (до max_candidates)
    scoring_embed_limit: int = 0
    embedding_batch_size: int = 64
    embedding_torch_threads: int = 0  # 0 = все доступные CPU-потоки

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = DEFAULT_CORS_ORIGINS
    session_ttl_hours: int = 720
    # Shared secret for GET /metrics/product (empty = endpoint disabled)
    metrics_token: str = ""

    tg_bot_token: str = ""
    telegram_web_app_url: str = "http://localhost:3001/tg"
    # False = бот без HTTPS_PROXY (если прокси не пускает api.telegram.org)
    telegram_bot_use_proxy: bool = True

    playlist_cover_enabled: bool = True
    openai_image_model: str = ""
    playlist_cover_aspect_ratio: str = "1:1"
    playlist_cover_resolution: str = "1K"
    playlist_cover_timeout_sec: float = 28.0
    cover_storage_dir: str = "data/covers"

    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    yandex_rate_limit_delay_sec: float = 0.15
    yandex_api_max_retries: int = 3
    device_flow_timeout_sec: int = 120

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url_sync(self) -> str:
        """Sync URL для Alembic (psycopg2)."""
        if "+asyncpg" in self.database_url:
            url = self.database_url.replace("+asyncpg", "+psycopg2")
        elif self.database_url.startswith("postgresql://"):
            url = self.database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        else:
            url = self.database_url
        return self._with_local_db_params(url)

    def _with_local_db_params(self, url: str) -> str:
        """connect_timeout + sslmode для localhost (иначе psycopg2 может висеть)."""
        if "localhost" not in url and "127.0.0.1" not in url:
            return url
        params: list[str] = []
        if "connect_timeout" not in url:
            params.append(f"connect_timeout={self.database_connect_timeout_sec}")
        if "sslmode" not in url:
            params.append("sslmode=disable")
        if not params:
            return url
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}{'&'.join(params)}"

    @property
    def database_is_local(self) -> bool:
        return "localhost" in self.database_url or "127.0.0.1" in self.database_url

    @property
    def retrieval(self) -> RetrievalSettings:
        return RetrievalSettings(
            max_candidates=self.max_candidates,
            min_candidates_pool=self.min_candidates_pool,
            target_candidates_pool=self.target_candidates_pool,
            artist_tracks_limit=self.artist_tracks_limit,
            search_tracks_per_query=self.search_tracks_per_query,
            search_pages=self.search_pages,
            search_expand_max_queries=self.search_expand_max_queries,
            retrieval_expand_passes=self.retrieval_expand_passes,
            min_clean_candidates=self.min_clean_candidates,
            similar_seeds_per_artist=self.similar_seeds_per_artist,
            max_similar_requests=self.max_similar_requests,
            reference_artists_tops_limit=self.reference_artists_tops_limit,
            discovered_artists_limit=self.discovered_artists_limit,
            discovered_similar_seeds=self.discovered_similar_seeds,
            feedback_artists_limit=self.feedback_artists_limit,
            feedback_similar_seeds=self.feedback_similar_seeds,
        )

    @property
    def library(self) -> LibrarySettings:
        return LibrarySettings(
            artist_limit=self.library_artist_limit,
            seed_artists=self.library_seed_artists,
            similar_seeds=self.library_similar_seeds,
            likes_track_limit=self.library_likes_track_limit,
            recent_full_models=self.library_recent_full_models,
            artist_boost=self.library_artist_boost,
        )

    @property
    def scoring(self) -> ScoringSettings:
        return ScoringSettings(
            embed_limit=self.scoring_embed_limit,
            batch_size=self.embedding_batch_size,
            torch_threads=self.embedding_torch_threads,
            max_tracks_per_artist=self.max_tracks_per_artist,
        )

    @property
    def yandex(self) -> YandexSettings:
        return YandexSettings(
            rate_limit_delay_sec=self.yandex_rate_limit_delay_sec,
            api_max_retries=self.yandex_api_max_retries,
            device_flow_timeout_sec=self.device_flow_timeout_sec,
        )


settings = Settings()
