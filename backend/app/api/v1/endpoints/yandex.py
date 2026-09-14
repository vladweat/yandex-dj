from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentSession, get_yandex_account_service
from app.core.exceptions import SecurityError, YandexMusicError
from app.db.models.session import Session
from app.schemas.yandex import YandexStatusResponse
from app.services.yandex_account_service import YandexAccountService

router = APIRouter(prefix="/yandex", tags=["yandex"])


@router.get("/account", response_model=YandexStatusResponse)
async def yandex_account(
    session: Session = CurrentSession,
    service: YandexAccountService = Depends(get_yandex_account_service),
) -> YandexStatusResponse:
    """Профиль из API Яндекс Музыки (yandex-music → account_status)."""
    try:
        return await service.get_account_status(session)
    except SecurityError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except YandexMusicError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
