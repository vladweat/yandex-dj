import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def disable_playlist_cover_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "playlist_cover_enabled", False)
