import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.client_channel import client_channel_from_request
from app.api.deps import CurrentSession, get_playlist_service
from app.api.playlist_http import raise_playlist_generate_http, raise_playlist_generate_timeout
from app.core.config import settings
from app.core.exceptions import (
    ExportError,
    LLMError,
    NotFoundError,
    QuotaExceededError,
    RetrievalError,
    ScoringError,
    YandexMusicError,
)
from app.core.security import decrypt_token
from app.db.models.session import Session
from app.schemas.playlist import (
    PlaylistFeedbackRequest,
    PlaylistFeedbackResponse,
    PlaylistGenerateRequest,
    PlaylistGenerateResponse,
    PlaylistHistoryResponse,
    PlaylistQuotaResponse,
)
from app.services.playlist_service import PlaylistService

router = APIRouter(prefix="/playlists", tags=["playlists"])


@router.get("", response_model=PlaylistHistoryResponse)
async def list_playlists(
    session: Session = CurrentSession,
    service: PlaylistService = Depends(get_playlist_service),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> PlaylistHistoryResponse:
    return await service.list_history(session.user_id, limit=limit, offset=offset)


@router.get("/quota", response_model=PlaylistQuotaResponse)
async def get_playlist_quota(
    session: Session = CurrentSession,
    service: PlaylistService = Depends(get_playlist_service),
) -> PlaylistQuotaResponse:
    return await service.get_quota(session.user_id)


@router.get("/{generation_id}", response_model=PlaylistGenerateResponse)
async def get_playlist(
    generation_id: uuid.UUID,
    session: Session = CurrentSession,
    service: PlaylistService = Depends(get_playlist_service),
) -> PlaylistGenerateResponse:
    try:
        return await service.get_generation(generation_id, session.user_id)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.patch("/{generation_id}/feedback", response_model=PlaylistFeedbackResponse)
async def set_playlist_feedback(
    generation_id: uuid.UUID,
    body: PlaylistFeedbackRequest,
    session: Session = CurrentSession,
    service: PlaylistService = Depends(get_playlist_service),
) -> PlaylistFeedbackResponse:
    try:
        return await service.set_feedback(
            generation_id,
            session.user_id,
            value=body.value,
        )
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/generate", response_model=PlaylistGenerateResponse)
async def generate_playlist(
    body: PlaylistGenerateRequest,
    request: Request,
    session: Session = CurrentSession,
    service: PlaylistService = Depends(get_playlist_service),
) -> PlaylistGenerateResponse:
    access_token = decrypt_token(session.encrypted_token)
    client_channel = client_channel_from_request(request)
    try:
        return await asyncio.wait_for(
            service.generate(
                prompt=body.prompt,
                track_count=body.track_count,
                instrumental_only=body.instrumental_only,
                access_token=access_token,
                login=session.user.login,
                user_id=session.user_id,
                exclude_artists=body.exclude_artists,
                exclude_languages=body.exclude_languages,
                diversity=body.diversity,
                use_library=body.use_library,
                source_id=body.source_id,
                client_channel=client_channel,
            ),
            timeout=settings.pipeline_timeout_sec,
        )
    except TimeoutError as exc:
        raise_playlist_generate_timeout(exc)
    except (
        QuotaExceededError,
        NotFoundError,
        LLMError,
        YandexMusicError,
        ExportError,
        RetrievalError,
        ScoringError,
    ) as exc:
        raise_playlist_generate_http(exc)
