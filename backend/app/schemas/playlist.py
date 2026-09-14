from pydantic import BaseModel, Field


class PlaylistGenerateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    track_count: int = Field(default=25, ge=1, le=50)
    instrumental_only: bool = False


class PlaylistTrackResponse(BaseModel):
    id: str
    title: str
    artist: str
    duration_ms: int
    similarity_score: float


class PlaylistGenerateResponse(BaseModel):
    title: str
    description: str
    playlist_url: str
    tracks: list[PlaylistTrackResponse]
