"""Лайки и история прослушивания."""

from yandex_music import ClientAsync, Track

from app.core.config import settings
from app.services.yandex.base import YandexApiBase


def _unique_preserve(names: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for name in names:
        key = name.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(name.strip())
        if len(result) >= limit:
            break
    return result


class YandexLibraryMixin(YandexApiBase):
    async def fetch_liked_tracks(
        self,
        client: ClientAsync,
        *,
        limit: int = 80,
    ) -> list[Track]:
        """Треки «Мне нравится» (ограниченный префикс списка)."""

        async def _fetch_ids() -> list[str | int]:
            await self._throttle()
            likes = await client.users_likes_tracks()
            if likes is None or not likes.tracks_ids:
                return []
            ids: list[str | int] = []
            for item in likes.tracks_ids[:limit]:
                track_id = item.id if hasattr(item, "id") else item
                if track_id is not None:
                    ids.append(track_id)
            return ids

        track_ids = await self._call_with_retry(_fetch_ids)
        if not track_ids:
            return []
        return await self.fetch_tracks(client, track_ids)

    async def fetch_liked_artist_names(
        self,
        client: ClientAsync,
        *,
        limit: int = 40,
    ) -> list[str]:
        async def _fetch() -> list[str]:
            await self._throttle()
            likes = await client.users_likes_artists()
            if not likes:
                return []
            names: list[str] = []
            for like in likes[:limit]:
                artist = like.artist
                if artist is not None and artist.name:
                    names.append(artist.name)
            return names

        return await self._call_with_retry(_fetch)

    async def fetch_recent_artist_names(
        self,
        client: ClientAsync,
        *,
        full_models_count: int = 40,
        limit: int = 40,
    ) -> list[str]:
        """Имена артистов из истории прослушивания (soft signal)."""

        async def _fetch_history():
            await self._throttle()
            return await client.music_history(full_models_count=full_models_count)

        history = await self._call_with_retry(_fetch_history)
        if history is None or not history.history_tabs:
            return []

        names: list[str] = []
        pending_ids: list[str | int] = []
        seen_ids: set[str] = set()

        for tab in history.history_tabs:
            for group in tab.items or []:
                for item in group.tracks or []:
                    data = item.data
                    if data is None:
                        continue
                    full = data.full_model
                    if full is not None and hasattr(full, "artists") and full.artists:
                        for artist in full.artists:
                            if artist and artist.name:
                                names.append(artist.name)
                        continue
                    item_id = data.item_id
                    if item_id is None:
                        continue
                    track_id = item_id.track_id or item_id.id
                    if track_id is None:
                        continue
                    key = str(track_id)
                    if key in seen_ids:
                        continue
                    seen_ids.add(key)
                    pending_ids.append(track_id)

        if pending_ids and len(names) < limit:
            tracks = await self.fetch_tracks(client, pending_ids[:limit])
            for track in tracks:
                for artist in track.artists or []:
                    if artist and artist.name:
                        names.append(artist.name)

        return _unique_preserve(names, limit)

    async def fetch_library_artist_names(
        self,
        access_token: str,
        *,
        limit: int | None = None,
        likes_track_limit: int | None = None,
        recent_full_models: int | None = None,
    ) -> list[str]:
        """Likes + recent → упорядоченный список имён артистов для soft bias."""
        library = settings.library
        client = await self.init_client(access_token)
        artist_cap = limit if limit is not None else library.artist_limit
        likes_cap = (
            likes_track_limit if likes_track_limit is not None else library.likes_track_limit
        )
        recent_cap = (
            recent_full_models if recent_full_models is not None else library.recent_full_models
        )

        liked_artists = await self.fetch_liked_artist_names(client, limit=artist_cap)
        liked_tracks = await self.fetch_liked_tracks(client, limit=likes_cap)
        recent_artists = await self.fetch_recent_artist_names(
            client,
            full_models_count=recent_cap,
            limit=artist_cap,
        )

        from_tracks: list[str] = []
        for track in liked_tracks:
            for artist in track.artists or []:
                if artist and artist.name:
                    from_tracks.append(artist.name)

        return _unique_preserve(
            [*liked_artists, *from_tracks, *recent_artists],
            artist_cap,
        )
