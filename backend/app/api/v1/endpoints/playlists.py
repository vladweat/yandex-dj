from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentSession, get_playlist_service
from app.core.exceptions import (
    ExportError,
    LLMError,
    RetrievalError,
    ScoringError,
    YandexMusicError,
)
from app.core.security import decrypt_token
from app.db.models.session import Session
from app.schemas.playlist import PlaylistGenerateRequest, PlaylistGenerateResponse
from app.services.playlist_service import PlaylistService

router = APIRouter(prefix="/playlists", tags=["playlists"])


@router.post("/generate", response_model=PlaylistGenerateResponse)
async def generate_playlist(
    body: PlaylistGenerateRequest,
    session: Session = CurrentSession,
    service: PlaylistService = Depends(get_playlist_service),
) -> PlaylistGenerateResponse:
    access_token = decrypt_token(session.encrypted_token)
    try:
        return await service.generate(
            body.prompt,
            body.track_count,
            body.instrumental_only,
            access_token,
            session.user.login,
        )
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
