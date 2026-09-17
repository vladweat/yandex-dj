"""Фасад API Яндекс Музыки."""

from app.services.yandex.auth import YandexAuthMixin
from app.services.yandex.catalog import YandexCatalogMixin
from app.services.yandex.export import PLAYLIST_URL_TEMPLATE, YandexExportMixin
from app.services.yandex.library import YandexLibraryMixin

__all__ = ["PLAYLIST_URL_TEMPLATE", "YandexMusicService"]


class YandexMusicService(
    YandexAuthMixin,
    YandexCatalogMixin,
    YandexLibraryMixin,
    YandexExportMixin,
):
    """Device Flow, каталог, библиотека, export плейлиста."""
