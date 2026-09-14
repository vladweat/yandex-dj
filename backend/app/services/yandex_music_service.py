"""Обёртка над yandex-music API: Device Flow, retry, rate limiting."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from yandex_music import ClientAsync, DeviceCode, OAuthToken, Status
from yandex_music.exceptions import DeviceAuthError, NetworkError, TimedOutError
from yandex_music.utils.request_async import Request

from app.core.config import settings
from app.core.exceptions import YandexMusicError
from app.core.proxy import get_outbound_proxy_url

T = TypeVar("T")


class YandexMusicService:
    def _create_client(self, token: str | None = None) -> ClientAsync:
        proxy_url = get_outbound_proxy_url()
        if proxy_url:
            return ClientAsync(token, request=Request(proxy_url=proxy_url))
        return ClientAsync(token)

    async def _call_with_retry(self, fn: Callable[[], Awaitable[T]]) -> T:
        last_exc: Exception | None = None
        for attempt in range(settings.yandex_api_max_retries):
            if attempt > 0:
                await asyncio.sleep(settings.yandex_rate_limit_delay_sec * (2**attempt))
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

    async def request_device_code(self) -> DeviceCode:
        client = self._create_client()

        async def _request() -> DeviceCode:
            return await client.request_device_code()

        return await self._call_with_retry(_request)

    async def poll_device_token(self, device_code: str) -> OAuthToken | None:
        client = self._create_client()

        async def _poll() -> OAuthToken | None:
            return await client.poll_device_token(device_code)

        return await self._call_with_retry(_poll)

    async def device_auth(
        self,
        on_code: Callable[[DeviceCode], Awaitable[None] | None],
        timeout: float | None = None,
    ) -> str:
        client = self._create_client()
        token = await client.device_auth(
            on_code=on_code,
            timeout=timeout or settings.device_flow_timeout_sec,
        )
        return token.access_token

    async def init_client(self, token: str) -> ClientAsync:
        client = self._create_client(token)

        async def _init() -> ClientAsync:
            await client.init()
            return client

        return await self._call_with_retry(_init)

    async def get_account_status(self, client: ClientAsync) -> Status:
        if client.me is not None:
            return client.me

        async def _status() -> Status:
            status = await client.account_status()
            if status is None:
                raise YandexMusicError("Failed to fetch account status")
            return status

        return await self._call_with_retry(_status)

    async def resolve_account(self, access_token: str) -> tuple[int, str]:
        """OAuth-токен → (yandex_uid, login)."""
        client = await self.init_client(access_token)
        status = await self.get_account_status(client)
        account = status.account
        if account is None or account.uid is None:
            raise YandexMusicError("Yandex account is missing in status response")
        return account.uid, account.login or str(account.uid)
