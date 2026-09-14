from pydantic import BaseModel, Field

from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate


class RetrievalRequest(BaseModel):
    profile: MusicProfile
    reference_track_id: str | None = Field(
        default=None,
        description="Опциональный ID трека-референса для tracks_similar",
    )


class RetrievalResponse(BaseModel):
    count: int
    elapsed_ms: int
    tracks: list[TrackCandidate]
