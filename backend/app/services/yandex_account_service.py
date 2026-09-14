from typing import Any

from app.core.security import decrypt_token
from app.db.models.session import Session
from app.schemas.yandex import YandexAccountSummary, YandexStatusResponse
from app.services.yandex_music_service import YandexMusicService


def _dict_field(raw: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = raw.get(key)
    return value if isinstance(value, dict) else None


class YandexAccountService:
    def __init__(self, yandex: YandexMusicService) -> None:
        self._yandex = yandex

    async def get_account_status(self, session: Session) -> YandexStatusResponse:
        access_token = decrypt_token(session.encrypted_token)
        raw: dict[str, Any] = await self._yandex.get_account_status_data(access_token)
        account_raw = raw.get("account")
        account = YandexAccountSummary(**account_raw) if isinstance(account_raw, dict) else None
        return YandexStatusResponse(
            account=account,
            default_email=raw.get("default_email"),
            subscription=_dict_field(raw, "subscription"),
            plus=_dict_field(raw, "plus"),
            permissions=_dict_field(raw, "permissions"),
            status=raw,
        )
