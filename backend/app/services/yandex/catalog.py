"""Поиск и загрузка треков из каталога."""

from collections.abc import Sequence

from yandex_music import ClientAsync, Track

from app.core.config import settings
from app.services.yandex.base import YandexApiBase


class YandexCatalogMixin(YandexApiBase):
    async def search_tracks(
        self,
        client: ClientAsync,
        query: str,
        *,
        limit: int | None = None,
        pages: int | None = None,
    ) -> list[Track]:
        retrieval = settings.retrieval
        per_query = limit or retrieval.search_tracks_per_query
        page_count = pages if pages is not None else retrieval.search_pages

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
        page_size = limit or settings.retrieval.artist_tracks_limit

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
