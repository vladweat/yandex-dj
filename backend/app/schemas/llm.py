from pydantic import BaseModel, Field


class MusicProfile(BaseModel):
    """Контракт LLM → пайплайн. См. docs/LLM_SCHEMA.md."""

    playlist_title: str = Field(description="Название плейлиста (2-4 слова)")
    playlist_description: str = Field(description="Короткое описание атмосферы")
    primary_genres: list[str] = Field(default_factory=list)
    mood_tags: list[str] = Field(default_factory=list)
    vocal_type: str = Field(description="'any' | 'instrumental_only' | 'vocal_only'")
    reference_artists: list[str] = Field(min_length=4, max_length=8)
    search_queries: list[str] = Field(min_length=3, max_length=5)
    target_track_count: int = Field(default=25, ge=1, le=50)


class ParsePromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    track_count: int | None = Field(default=None, ge=1, le=50)
    instrumental_only: bool = False


class ParsePromptResponse(BaseModel):
    profile: MusicProfile
