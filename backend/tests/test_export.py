from unittest.mock import AsyncMock, MagicMock

import pytest
from app.services.yandex_music_service import YandexMusicService
from yandex_music import Album, Track


def _track(track_id: str, album_id: str) -> Track:
    album = Album(id=int(album_id), title="Album")
    track = Track(id=int(track_id), title="Nightcall", albums=[album])
    return track


@pytest.mark.asyncio
async def test_resolve_track_refs_preserves_order() -> None:
    service = YandexMusicService()
    client = MagicMock()
    service.fetch_tracks = AsyncMock(return_value=[_track("2", "20"), _track("1", "10")])

    refs = await service.resolve_track_refs(client, ["1", "2"])

    assert refs == [("1", "10"), ("2", "20")]


@pytest.mark.asyncio
async def test_export_playlist_creates_and_populates() -> None:
    service = YandexMusicService()
    client = MagicMock()
    playlist = MagicMock(kind=1003, revision=1)

    service.resolve_track_refs = AsyncMock(return_value=[("1", "10")])
    service.create_user_playlist = AsyncMock(return_value=playlist)
    service.populate_playlist = AsyncMock()
    service.set_playlist_description = AsyncMock()

    url = await service.export_playlist(
        client,
        title="Night Drive",
        description="Dark synthwave",
        track_ids=["1"],
        login="testuser",
    )

    assert url == "https://music.yandex.ru/users/testuser/playlists/1003"
    service.create_user_playlist.assert_awaited_once_with(client, "Night Drive")
    service.populate_playlist.assert_awaited_once_with(client, playlist, [("1", "10")])
    service.set_playlist_description.assert_awaited_once_with(client, 1003, "Dark synthwave")


@pytest.mark.asyncio
async def test_populate_playlist_uses_single_change_diff() -> None:
    service = YandexMusicService()
    client = MagicMock()
    client.users_playlists_change = AsyncMock(return_value=MagicMock(kind=1, revision=2))
    service._throttle = AsyncMock()
    playlist = MagicMock(kind=42, revision=1)

    await service.populate_playlist(
        client,
        playlist,
        [("11", "100"), ("12", "200")],
    )

    client.users_playlists_change.assert_awaited_once()
    args, kwargs = client.users_playlists_change.await_args
    assert args[0] == 42
    assert kwargs.get("revision") == 1
    diff = args[1]
    assert "11" in diff and "12" in diff
    assert "100" in diff and "200" in diff
