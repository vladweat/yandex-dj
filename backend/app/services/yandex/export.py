"""Создание и наполнение плейлистов."""

import logging
from collections.abc import Sequence

from yandex_music import ClientAsync, Playlist
from yandex_music.utils.difference import Difference

from app.core.exceptions import ExportError, YandexMusicError
from app.core.generation_usage import record_yandex_api_call
from app.services.yandex.base import YandexApiBase

logger = logging.getLogger(__name__)

PLAYLIST_URL_TEMPLATE = "https://music.yandex.ru/users/{login}/playlists/{kind}"


def _playlist_track_count(playlist: Playlist) -> int:
    """Число треков в плейлисте (API часто отдаёт усечённый `tracks`, есть `track_count`)."""
    if playlist.track_count is not None and playlist.track_count > 0:
        return int(playlist.track_count)
    return len(playlist.tracks or [])


class YandexExportMixin(YandexApiBase):
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
        """Одна операция change (Difference) вместо N insert_track — сильно быстрее под proxy."""
        if playlist.kind is None or playlist.revision is None:
            raise ExportError("Invalid playlist response from Yandex API")
        if not track_refs:
            return

        tracks_payload = [
            {"id": track_id, "album_id": album_id} for track_id, album_id in track_refs
        ]
        diff = Difference().add_insert(at=0, tracks=tracks_payload).to_json()

        async def _change() -> Playlist:
            await self._throttle()
            updated = await client.users_playlists_change(
                playlist.kind,
                diff,
                revision=playlist.revision,
            )
            if updated is None:
                raise YandexMusicError("Failed to populate playlist via change")
            return updated

        await self._call_with_retry(_change)

    async def _apply_playlist_diff(
        self,
        client: ClientAsync,
        kind: str | int,
        diff: Difference,
    ) -> None:
        if not diff.operations:
            return

        async def _change() -> None:
            await self._throttle()
            playlist = await client.users_playlists(kind)
            if playlist is None or playlist.revision is None:
                raise YandexMusicError("Playlist not found")
            record_yandex_api_call()
            updated = await client.users_playlists_change(
                kind,
                diff.to_json(),
                revision=playlist.revision,
            )
            if updated is None:
                raise YandexMusicError("Failed to update playlist tracks")

        await self._call_with_retry(_change)

    async def delete_playlist_track_at(
        self,
        client: ClientAsync,
        kind: str | int,
        at: int,
    ) -> None:
        """Удалить один трек по индексу (тот же порядок, что при export)."""
        diff = Difference().add_delete(at, at)
        await self._apply_playlist_diff(client, kind, diff)

    async def replace_playlist_track_at(
        self,
        client: ClientAsync,
        kind: str | int,
        at: int,
        track_id: str | int,
    ) -> None:
        refs = await self.resolve_track_refs(client, [track_id])
        if not refs:
            raise ExportError("No tracks available for export")
        track_id_ref, album_id = refs[0]
        diff = Difference().add_delete(at, at)
        diff.add_insert(at, {"id": track_id_ref, "album_id": album_id})
        await self._apply_playlist_diff(client, kind, diff)

    async def replace_playlist_contents(
        self,
        client: ClientAsync,
        kind: str | int,
        track_ids: Sequence[str | int],
    ) -> None:
        """Полная замена треков в существующем плейлисте ."""
        track_refs = await self.resolve_track_refs(client, track_ids)
        if track_ids and not track_refs:
            raise ExportError("No tracks available for export")

        async def _replace() -> None:
            await self._throttle()
            playlist = await client.users_playlists(kind)
            if playlist is None or playlist.revision is None:
                raise YandexMusicError("Playlist not found")
            existing_count = _playlist_track_count(playlist)
            diff = Difference()
            if existing_count > 0:
                diff.add_delete(0, existing_count - 1)
            if track_refs:
                tracks_payload = [
                    {"id": track_id, "album_id": album_id} for track_id, album_id in track_refs
                ]
                diff.add_insert(at=0, tracks=tracks_payload)
            if not diff.operations:
                return
            record_yandex_api_call()
            updated = await client.users_playlists_change(
                kind,
                diff.to_json(),
                revision=playlist.revision,
            )
            if updated is None:
                raise YandexMusicError("Failed to update playlist tracks")

        await self._call_with_retry(_replace)

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
