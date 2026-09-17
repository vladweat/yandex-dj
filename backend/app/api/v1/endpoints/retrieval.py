import time

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentSession, get_retrieval_service
from app.core.exceptions import RetrievalError, YandexMusicError
from app.core.security import decrypt_token
from app.core.timing import elapsed_ms_since
from app.db.models.session import Session
from app.schemas.retrieval import RetrievalRequest, RetrievalResponse
from app.services.retrieval_service import RetrievalService

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/candidates", response_model=RetrievalResponse)
async def collect_candidates(
    body: RetrievalRequest,
    session: Session = CurrentSession,
    retrieval: RetrievalService = Depends(get_retrieval_service),
) -> RetrievalResponse:
    access_token = decrypt_token(session.encrypted_token)
    started = time.perf_counter()
    try:
        tracks = await retrieval.collect_candidates(
            body.profile,
            access_token,
            reference_track_id=body.reference_track_id,
        )
    except YandexMusicError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except RetrievalError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    elapsed_ms = elapsed_ms_since(started)
    return RetrievalResponse(count=len(tracks), elapsed_ms=elapsed_ms, tracks=tracks)
