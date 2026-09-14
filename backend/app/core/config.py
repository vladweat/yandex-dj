from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    playlist_size: int = 25
    max_tracks_per_artist: int = 2
    pipeline_timeout_sec: int = 12
    track_cache_ttl_sec: int = 86400
    artist_tracks_limit: int = 10
    search_tracks_per_query: int = 50
    search_pages: int = 2
    search_expand_max_queries: int = 12
    retrieval_expand_passes: int = 2
    scoring_embed_limit: int = 80
    embedding_batch_size: int = 64
    embedding_torch_threads: int = 0  # 0 = все доступные CPU-потоки

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = DEFAULT_CORS_ORIGINS
    session_ttl_hours: int = 720

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


settings = Settings()
