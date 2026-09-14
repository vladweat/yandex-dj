from fastapi import APIRouter, Depends

from app.api.deps import get_health_service
from app.schemas.health import HealthResponse
from app.services.health_service import HealthService

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(service: HealthService = Depends(get_health_service)) -> HealthResponse:
    return await service.get_status()
