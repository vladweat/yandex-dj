from fastapi import APIRouter, Depends, Query

from app.api.deps import get_metrics_service, require_metrics_token
from app.schemas.metrics import ProductMetricsResponse
from app.services.metrics_service import MetricsService

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/product", response_model=ProductMetricsResponse)
async def product_metrics(
    _: None = Depends(require_metrics_token),
    service: MetricsService = Depends(get_metrics_service),
    days: int = Query(default=7, ge=1, le=90),
) -> ProductMetricsResponse:
    """Admin report: p50/p95 latency, full-N, warnings, regen, return-7d ."""
    return await service.product_metrics(days=days)
