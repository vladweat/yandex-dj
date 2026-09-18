from pydantic import BaseModel, Field

# 0 = search; 1 = anchor/discovered tops; 2 = similar (apply_expansion_prior)
RETRIEVAL_TIER_SEARCH = 0
RETRIEVAL_TIER_ANCHOR = 1
RETRIEVAL_TIER_SIMILAR = 2


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
    explicit: bool | None = None
    retrieval_tier: int = RETRIEVAL_TIER_SEARCH

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

    def embedding_passport(self) -> str:
        """Короткий текст для embedding — меньше токенов, быстрее batch-encode."""
        artists = ", ".join(self.artists)
        parts = [self.title, artists]
        if self.genre:
            parts.append(self.genre)
        return ". ".join(parts)
