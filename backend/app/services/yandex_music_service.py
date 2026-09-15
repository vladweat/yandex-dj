"""Обёртка над yandex-music API: Device Flow, retry, rate limiting."""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar

from yandex_music import ClientAsync, DeviceCode, OAuthToken, Playlist, Status, Track
from yandex_music.exceptions import DeviceAuthError, NetworkError, TimedOutError
from yandex_music.utils.request_async import Request

from app.core.config import settings
from app.core.exceptions import ExportError, YandexMusicError
from app.core.proxy import get_outbound_proxy_url

T = TypeVar("T")

logger = logging.getLogger(__name__)

PLAYLIST_URL_TEMPLATE = "https://music.yandex.ru/users/{login}/playlists/{kind}"


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

    async def get_account_status_data(self, access_token: str) -> dict:
        """OAuth-токен → account/status (сериализация Status.to_dict())."""
        client = await self.init_client(access_token)
        status = await self.get_account_status(client)
        return status.to_dict()

    async def _throttle(self) -> None:
        await asyncio.sleep(settings.yandex_rate_limit_delay_sec)

    async def search_tracks(
        self,
        client: ClientAsync,
        query: str,
        *,
        limit: int | None = None,
        pages: int | None = None,
    ) -> list[Track]:
        per_query = limit or settings.search_tracks_per_query
        page_count = pages if pages is not None else settings.search_pages

        async def _search() -> list[Track]:
            tracks: list[Track] = []
            seen_ids: set[str] = set()

            for page in range(page_count):
                await self._throttle()
                result = await client.search(query, type_="track", page=page)
                if result is None or result.tracks is None or not result.tracks.results:
                    break

                for track in result.tracks.results:
                    if track.id is None:
                        continue
                    track_id = str(track.id)
                    if track_id in seen_ids:
                        continue
                    seen_ids.add(track_id)
                    tracks.append(track)
                    if len(tracks) >= per_query:
                        return tracks

                per_page = result.tracks.per_page or len(result.tracks.results)
                if len(result.tracks.results) < per_page:
                    break

            return tracks

        return await self._call_with_retry(_search)

    async def search_artist_id(self, client: ClientAsync, name: str) -> str | None:
        async def _search() -> str | None:
            await self._throttle()
            result = await client.search(name, type_="artist")
            if result is None or result.artists is None or not result.artists.results:
                return None
            artist = result.artists.results[0]
            if artist.id is None:
                return None
            return str(artist.id)

        return await self._call_with_retry(_search)

    async def artists_top_tracks(
        self,
        client: ClientAsync,
        artist_id: str | int,
        *,
        limit: int | None = None,
    ) -> list[Track]:
        page_size = limit or settings.artist_tracks_limit

        async def _fetch() -> list[Track]:
            await self._throttle()
            result = await client.artists_tracks(artist_id, page=0, page_size=page_size)
            if result is None or not result.tracks:
                return []
            return list(result.tracks[:page_size])

        return await self._call_with_retry(_fetch)

    async def tracks_similar_list(
        self,
        client: ClientAsync,
        track_id: str | int,
    ) -> list[Track]:
        async def _fetch() -> list[Track]:
            await self._throttle()
            result = await client.tracks_similar(track_id)
            if result is None or not result.similar_tracks:
                return []
            return list(result.similar_tracks)

        return await self._call_with_retry(_fetch)

    async def fetch_tracks(
        self,
        client: ClientAsync,
        track_ids: Sequence[str | int],
    ) -> list[Track]:
        if not track_ids:
            return []

        async def _fetch() -> list[Track]:
            await self._throttle()
            tracks = await client.tracks(list(track_ids))
            return [track for track in tracks if track is not None]

        return await self._call_with_retry(_fetch)

    async def create_user_playlist(self, client: ClientAsync, title: str) -> Playlist:
        async def _create() -> Playlist:
            await self._throttle()
            playlist = await client.users_playlists_create(title=title)
            if playlist is None or playlist.kind is None or playlist.revision is None:
                raise YandexMusicError("Failed to create playlist")
            return playlist

        return await self._call_with_retry(_create)

    async def set_playlist_description(
        self,
        client: ClientAsync,
        kind: str | int,
        description: str,
    ) -> None:
        async def _set_description() -> Playlist:
            await self._throttle()
            playlist = await client.users_playlists_description(kind, description)
            if playlist is None:
                raise YandexMusicError("Failed to set playlist description")
            return playlist

        await self._call_with_retry(_set_description)

    async def resolve_track_refs(
        self,
        client: ClientAsync,
        track_ids: Sequence[str | int],
    ) -> list[tuple[str, str]]:
        """track_id → (track_id, album_id) для users_playlists_insert_track."""
        if not track_ids:
            return []

        tracks = await self.fetch_tracks(client, list(track_ids))
        by_id = {str(track.id): track for track in tracks if track.id is not None}

        refs: list[tuple[str, str]] = []
        for raw_id in track_ids:
            track_id = str(raw_id)
            track = by_id.get(track_id)
            if track is None:
                logger.warning("Track %s not found during export resolve", track_id)
                continue
            album_id = ""
            if track.albums:
                first_album = track.albums[0]
                if first_album.id is not None:
                    album_id = str(first_album.id)
            if not album_id:
                logger.warning("Track %s has no album_id, skipping export", track_id)
                continue
            refs.append((track_id, album_id))
        return refs

    async def populate_playlist(
        self,
        client: ClientAsync,
        playlist: Playlist,
        track_refs: Sequence[tuple[str, str]],
    ) -> None:
        if playlist.kind is None or playlist.revision is None:
            raise ExportError("Invalid playlist response from Yandex API")

        revision = playlist.revision
        for index, (track_id, album_id) in enumerate(track_refs):
            revision = await self._insert_playlist_track(
                client,
                playlist.kind,
                track_id,
                album_id,
                at=index,
                revision=revision,
            )

    async def _insert_playlist_track(
        self,
        client: ClientAsync,
        kind: str | int,
        track_id: str,
        album_id: str,
        *,
        at: int,
        revision: int,
    ) -> int:
        async def _insert() -> int:
            await self._throttle()
            updated = await client.users_playlists_insert_track(
                kind,
                track_id,
                album_id,
                at=at,
                revision=revision,
            )
            if updated is None or updated.revision is None:
                raise YandexMusicError(f"Failed to insert track {track_id}")
            return updated.revision

        return await self._call_with_retry(_insert)

    @staticmethod
    def playlist_url(login: str, kind: str | int) -> str:
        return PLAYLIST_URL_TEMPLATE.format(login=login, kind=kind)

    async def export_playlist(
        self,
        client: ClientAsync,
        *,
        title: str,
        description: str,
        track_ids: Sequence[str | int],
        login: str,
    ) -> str:
        track_refs = await self.resolve_track_refs(client, track_ids)
        if not track_refs:
            raise ExportError("No tracks available for export")

        playlist = await self.create_user_playlist(client, title)
        await self.populate_playlist(client, playlist, track_refs)
        await self.set_playlist_description(client, playlist.kind, description)
        return self.playlist_url(login, playlist.kind)
