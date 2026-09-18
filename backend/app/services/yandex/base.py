"""HTTP-клиент Яндекс Музыки: proxy, retry, throttle."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from yandex_music import ClientAsync
from yandex_music.exceptions import DeviceAuthError, NetworkError, TimedOutError
from yandex_music.utils.request_async import Request

from app.core.config import settings
from app.core.exceptions import YandexMusicError
from app.core.generation_usage import record_yandex_api_call
from app.core.proxy import get_outbound_proxy_url

T = TypeVar("T")

logger = logging.getLogger(__name__)


class YandexApiBase:
    def _create_client(self, token: str | None = None) -> ClientAsync:
        proxy_url = get_outbound_proxy_url()
        if proxy_url:
            return ClientAsync(token, request=Request(proxy_url=proxy_url))
        return ClientAsync(token)

    async def _call_with_retry(self, fn: Callable[[], Awaitable[T]]) -> T:
        yandex = settings.yandex
        last_exc: Exception | None = None
        for attempt in range(yandex.api_max_retries):
            if attempt > 0:
                await asyncio.sleep(yandex.rate_limit_delay_sec * (2**attempt))
            try:
                return await fn()
            except DeviceAuthError:
                raise
            except (NetworkError, TimedOutError) as exc:
                last_exc = exc

        hint = ""
        if get_outbound_proxy_url() is None:
            hint = " Проверьте HTTPS_PROXY (см. .env.example)."
        raise YandexMusicError(f"{last_exc}{hint}") from last_exc

    async def _throttle(self) -> None:
        record_yandex_api_call()
        await asyncio.sleep(settings.yandex.rate_limit_delay_sec)
