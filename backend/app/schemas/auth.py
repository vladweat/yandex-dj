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
