from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate


class ScoredTrack(BaseModel):
    id: str
    title: str
    artists: list[str] = Field(default_factory=list)
    album: str = ""
    genre: str = ""
    duration_ms: int = 0
    score: float

    @classmethod
    def from_candidate(cls, track: TrackCandidate, score: float) -> ScoredTrack:
        return cls(
            id=track.id,
            title=track.title,
            artists=track.artists,
            album=track.album,
            genre=track.genre,
            duration_ms=track.duration_ms,
            score=round(score, 4),
        )


class ScoringRequest(BaseModel):
    profile: MusicProfile
    candidates: list[TrackCandidate] = Field(min_length=1)
    prompt: str | None = Field(
        default=None,
        description="Исходный промпт пользователя (дополняет embedding query)",
    )


class ScoringResponse(BaseModel):
    count: int
    elapsed_ms: int
    method: str
    tracks: list[ScoredTrack]
