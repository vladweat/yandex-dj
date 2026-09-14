from typing import Any

from pydantic import BaseModel, Field


class YandexAccountSummary(BaseModel):
    uid: int | None = None
    login: str | None = None
    display_name: str | None = None
    full_name: str | None = None
    first_name: str | None = None
    second_name: str | None = None
    service_available: bool | None = None
    region: int | None = None
    registered_at: str | None = None
    child: bool | None = None


class YandexStatusResponse(BaseModel):
    """account/status из yandex-music (ClientAsync.account_status)."""

    account: YandexAccountSummary | None = None
    default_email: str | None = None
    subscription: dict[str, Any] | None = None
    plus: dict[str, Any] | None = None
    permissions: dict[str, Any] | None = None
    status: dict[str, Any] = Field(description="Полный ответ библиотеки (Status.to_dict())")
