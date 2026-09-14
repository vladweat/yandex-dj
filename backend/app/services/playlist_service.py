"""Оркестрация пайплайна: LLM → retrieval → scoring → export."""

from app.schemas.playlist import PlaylistGenerateResponse


class PlaylistService:
    async def generate(
        self,
        prompt: str,
        track_count: int,
        instrumental_only: bool,
    ) -> PlaylistGenerateResponse:
        raise NotImplementedError
