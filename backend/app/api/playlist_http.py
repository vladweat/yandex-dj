"""HTTP-маппинг ошибок пайплайна для POST /playlists/generate."""

from fastapi import HTTPException, status

from app.core.config import settings
from app.core.exceptions import (
    ExportError,
    LLMError,
    NotFoundError,
    PipelineTimeoutError,
    QuotaExceededError,
    RetrievalError,
    ScoringError,
    YandexMusicError,
)


def raise_playlist_generate_http(exc: BaseException) -> None:
    """Пробрасывает HTTPException с теми же кодами, что и generate endpoint."""
    if isinstance(exc, QuotaExceededError):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": str(exc),
                "limit": exc.limit,
                "used": exc.used,
                "remaining": exc.remaining,
                "resets_at": exc.resets_at,
            },
        ) from exc
    if isinstance(exc, NotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    if isinstance(exc, LLMError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    if isinstance(exc, YandexMusicError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    if isinstance(exc, ExportError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    if isinstance(exc, RetrievalError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    if isinstance(exc, ScoringError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    raise exc


def raise_playlist_generate_timeout(exc: TimeoutError) -> None:
    raise HTTPException(
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        detail=(
            f"Playlist generation exceeded {settings.pipeline_timeout_sec}s (PIPELINE_TIMEOUT_SEC)"
        ),
    ) from PipelineTimeoutError(str(exc))
