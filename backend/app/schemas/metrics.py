from pydantic import BaseModel, Field


class ProductMetricsResponse(BaseModel):
    """Aggregated product metrics over playlist_generations (P0.4)."""

    window_days: int = Field(ge=1, le=90)
    total_generations: int
    latency_p50_ms: float | None = None
    latency_p95_ms: float | None = None
    latency_avg_ms: float | None = None
    full_n_rate: float | None = None
    warnings_rate: float | None = None
    regen_rate: float | None = None
    return_7d: float | None = None
    like_rate: float | None = None
    dislike_rate: float | None = None
    avg_clean: float | None = None
    with_latency: int = 0
    with_feedback: int = 0
    regen_count: int = 0
    returning_users: int = 0
    active_users: int = 0
    generations_telegram: int = 0
    generations_web: int = 0
