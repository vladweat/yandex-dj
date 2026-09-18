from datetime import datetime

from pydantic import BaseModel


class DeviceFlowStartResponse(BaseModel):
    device_code: str
    user_code: str
    verification_url: str
    expires_in: int
    interval: int


class DeviceFlowPollRequest(BaseModel):
    device_code: str


class DeviceFlowPollResponse(BaseModel):
    status: str
    session_id: str | None = None


class AuthMeResponse(BaseModel):
    session_id: str
    login: str
    yandex_uid: int
    expires_at: datetime
    telegram_user_id: int | None = None


class TelegramLinkRequest(BaseModel):
    init_data: str


class TelegramLinkResponse(BaseModel):
    telegram_user_id: int
