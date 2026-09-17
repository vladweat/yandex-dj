import time

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_scoring_service
from app.core.exceptions import ScoringError
from app.core.timing import elapsed_ms_since
from app.schemas.scoring import ScoringRequest, ScoringResponse
from app.services.scoring_service import ScoringService

router = APIRouter(prefix="/scoring", tags=["scoring"])


@router.post("/rank", response_model=ScoringResponse)
async def rank_tracks(
    body: ScoringRequest,
    scoring: ScoringService = Depends(get_scoring_service),
) -> ScoringResponse:
    started = time.perf_counter()
    try:
        tracks, method = await scoring.rank(
            body.profile,
            body.candidates,
            user_prompt=body.prompt,
        )
    except ScoringError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    elapsed_ms = elapsed_ms_since(started)
    return ScoringResponse(
        count=len(tracks),
        elapsed_ms=elapsed_ms,
        method=method,
        tracks=tracks,
    )
