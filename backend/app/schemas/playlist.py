import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.llm import MusicProfile

DiversityMode = Literal["normal", "high"]
FeedbackValue = Literal["like", "dislike"]
TrackEditAction = Literal["remove", "replace"]


class PlaylistGenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    track_count: int = Field(default=25, ge=1, le=50)
    instrumental_only: bool = False
    exclude_artists: list[str] = Field(default_factory=list, max_length=20)
    exclude_languages: list[str] = Field(default_factory=list, max_length=5)
    diversity: DiversityMode = "normal"
    use_library: bool = False
    source_id: uuid.UUID | None = None


class PlaylistFeedbackRequest(BaseModel):
    value: FeedbackValue | None = None


class PlaylistTrackEditRequest(BaseModel):
    track_id: str = Field(min_length=1)
    action: TrackEditAction = "replace"


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
    exclude_languages: list[str] = Field(default_factory=list)
    diversity: DiversityMode = "normal"
    use_library: bool = False


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
    source_id: uuid.UUID | None = None
    latency_ms: int | None = None
    feedback: FeedbackValue | None = None
    has_cover: bool = False


class PlaylistHistoryItem(BaseModel):
    id: uuid.UUID
    prompt: str
    title: str
    playlist_url: str
    pool_stats: PlaylistPoolStats | None = None
    options: PlaylistGenerationOptions | None = None
    created_at: datetime
    source_id: uuid.UUID | None = None
    latency_ms: int | None = None
    feedback: FeedbackValue | None = None


class PlaylistHistoryResponse(BaseModel):
    items: list[PlaylistHistoryItem]
    limit: int
    offset: int


class PlaylistFeedbackResponse(BaseModel):
    id: uuid.UUID
    feedback: FeedbackValue | None = None
    feedback_at: datetime | None = None


class PlaylistQuotaResponse(BaseModel):
    """Soft-квота новых генераций за UTC-сутки. «Ещё вариант» не расходует."""

    limit: int
    used: int
    remaining: int
    unlimited: bool
    resets_at: datetime
