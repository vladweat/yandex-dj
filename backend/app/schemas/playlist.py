import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.llm import MusicProfile

DiversityMode = Literal["normal", "high"]


class PlaylistGenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    track_count: int = Field(default=25, ge=1, le=50)
    instrumental_only: bool = False
    exclude_artists: list[str] = Field(default_factory=list, max_length=20)
    diversity: DiversityMode = "normal"
    source_id: uuid.UUID | None = None


class PlaylistTrackResponse(BaseModel):
    id: str
    title: str
    artist: str
    duration_ms: int
    similarity_score: float


class PlaylistPoolStats(BaseModel):
    raw: int
    clean: int
    selected: int


class PlaylistGenerationOptions(BaseModel):
    track_count: int = 25
    instrumental_only: bool = False
    exclude_artists: list[str] = Field(default_factory=list)
    diversity: DiversityMode = "normal"


class PlaylistGenerateResponse(BaseModel):
    id: uuid.UUID
    prompt: str
    title: str
    description: str
    playlist_url: str
    tracks: list[PlaylistTrackResponse]
    pool_stats: PlaylistPoolStats | None = None
    profile: MusicProfile
    options: PlaylistGenerationOptions | None = None
    warnings: list[str] = Field(default_factory=list)


class PlaylistHistoryItem(BaseModel):
    id: uuid.UUID
    prompt: str
    title: str
    playlist_url: str
    pool_stats: PlaylistPoolStats | None = None
    options: PlaylistGenerationOptions | None = None
    created_at: datetime


class PlaylistHistoryResponse(BaseModel):
    items: list[PlaylistHistoryItem]
    limit: int
    offset: int
