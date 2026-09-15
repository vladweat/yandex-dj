import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentSession, get_playlist_service
from app.core.exceptions import (
    ExportError,
    LLMError,
    NotFoundError,
    RetrievalError,
    ScoringError,
    YandexMusicError,
)
from app.core.security import decrypt_token
from app.db.models.session import Session
from app.schemas.playlist import (
    PlaylistGenerateRequest,
    PlaylistGenerateResponse,
    PlaylistHistoryResponse,
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


@router.post("/generate", response_model=PlaylistGenerateResponse)
async def generate_playlist(
    body: PlaylistGenerateRequest,
    session: Session = CurrentSession,
    service: PlaylistService = Depends(get_playlist_service),
) -> PlaylistGenerateResponse:
    access_token = decrypt_token(session.encrypted_token)
    try:
        return await service.generate(
            prompt=body.prompt,
            track_count=body.track_count,
            instrumental_only=body.instrumental_only,
            access_token=access_token,
            login=session.user.login,
            user_id=session.user_id,
            exclude_artists=body.exclude_artists,
            diversity=body.diversity,
            source_id=body.source_id,
        )
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except LLMError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except YandexMusicError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except ExportError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except RetrievalError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ScoringError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
