from pydantic import BaseModel, Field


class TrackCandidate(BaseModel):
    """Нормализованный трек из каталога Яндекс Музыки."""

    id: str
    title: str
    artists: list[str] = Field(default_factory=list)
    album: str = ""
    genre: str = ""
    version: str = ""
    duration_ms: int = 0
    available: bool = True

    @property
    def artist_title_key(self) -> str:
        artist = self.artists[0] if self.artists else ""
        return f"{artist}|{self.title}".lower()

    def passport(self) -> str:
        artists = ", ".join(self.artists)
        return (
            f"Название: {self.title}. "
            f"Исполнитель: {artists}. "
            f"Альбом: {self.album}. "
            f"Жанр: {self.genre}. "
            f"Версия: {self.version}"
        )
