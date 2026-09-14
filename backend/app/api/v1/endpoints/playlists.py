from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_playlist_service
from app.schemas.playlist import PlaylistGenerateRequest, PlaylistGenerateResponse
from app.services.playlist_service import PlaylistService

router = APIRouter(prefix="/playlists", tags=["playlists"])


@router.post("/generate", response_model=PlaylistGenerateResponse)
async def generate_playlist(
    body: PlaylistGenerateRequest,
    _service: PlaylistService = Depends(get_playlist_service),
) -> PlaylistGenerateResponse:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Генерация плейлиста — в разработке",
    )
