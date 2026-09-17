from datetime import UTC, datetime, timedelta

from app.repositories.playlist_generation_repository import PlaylistGenerationRepository
from app.schemas.metrics import ProductMetricsResponse


class MetricsService:
    def __init__(self, repo: PlaylistGenerationRepository) -> None:
        self._repo = repo

    async def product_metrics(self, *, days: int = 7) -> ProductMetricsResponse:
        since = datetime.now(UTC) - timedelta(days=days)
        row = await self._repo.aggregate_product_metrics(since=since)
        return ProductMetricsResponse(window_days=days, **row)
