from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentSession, get_auth_service
from app.core.exceptions import AuthError, YandexMusicError
from app.db.models.session import Session
from app.schemas.auth import (
    AuthMeResponse,
    DeviceFlowPollRequest,
    DeviceFlowPollResponse,
    DeviceFlowStartResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/device-flow/start", response_model=DeviceFlowStartResponse)
async def device_flow_start(
    service: AuthService = Depends(get_auth_service),
) -> DeviceFlowStartResponse:
    try:
        return await service.start_device_flow()
    except YandexMusicError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("/device-flow/poll", response_model=DeviceFlowPollResponse)
async def device_flow_poll(
    body: DeviceFlowPollRequest,
    service: AuthService = Depends(get_auth_service),
) -> DeviceFlowPollResponse:
    try:
        return await service.poll_device_flow(body.device_code)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except YandexMusicError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/me", response_model=AuthMeResponse)
async def auth_me(session: Session = CurrentSession) -> AuthMeResponse:
    return AuthMeResponse(
        session_id=str(session.id),
        login=session.user.login,
        yandex_uid=session.user.yandex_uid,
        expires_at=session.expires_at,
    )
