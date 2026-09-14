"""Парсинг промпта → MusicProfile через OpenAI + instructor (KodikRouter-compatible)."""

from __future__ import annotations

from typing import Any

import instructor
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.exceptions import LLMError
from app.core.llm_config import openai_is_configured, resolve_openai_base_url, resolve_openai_model
from app.schemas.llm import MusicProfile
from app.services.llm_prompts import build_messages
from app.utils.search_queries import refine_search_queries

LLM_MAX_RETRIES = 2
LLM_TIMEOUT_SEC = 60.0


def enrich_search_queries(profile: MusicProfile) -> MusicProfile:
    """Дополнить search_queries из жанров и mood, если LLM вернул меньше 3."""
    if len(profile.search_queries) >= 3:
        return refine_search_queries(profile)

    queries = list(profile.search_queries)
    seen = {item.lower() for item in queries}

    for genre in profile.primary_genres:
        candidate = genre.strip()
        if candidate and candidate.lower() not in seen:
            queries.append(candidate)
            seen.add(candidate.lower())
        if len(queries) >= 3:
            break

    if len(queries) < 3:
        for tag in profile.mood_tags:
            candidate = tag.strip()
            if candidate and candidate.lower() not in seen:
                queries.append(candidate)
                seen.add(candidate.lower())
            if len(queries) >= 3:
                break

    if len(queries) == len(profile.search_queries):
        return profile

    profile = profile.model_copy(update={"search_queries": queries[:5]})
    return refine_search_queries(profile)


def apply_request_hints(
    profile: MusicProfile,
    *,
    track_count: int | None,
    instrumental_only: bool,
) -> MusicProfile:
    updates: dict[str, Any] = {}
    if track_count is not None:
        updates["target_track_count"] = track_count
    if instrumental_only:
        updates["vocal_type"] = "instrumental_only"
    if updates:
        profile = profile.model_copy(update=updates)
    return enrich_search_queries(profile)


class LLMService:
    def __init__(self, *, client: Any | None = None) -> None:
        self._injected_client = client

    def _create_client(self) -> Any:
        if self._injected_client is not None:
            return self._injected_client
        if not openai_is_configured():
            raise LLMError("OPENAI_API_KEY is not configured")
        openai_client = AsyncOpenAI(
            api_key=settings.openai_api_key.strip(),
            base_url=resolve_openai_base_url(),
            timeout=LLM_TIMEOUT_SEC,
        )
        return instructor.from_openai(openai_client)

    async def parse_prompt(
        self,
        prompt: str,
        *,
        track_count: int | None = None,
        instrumental_only: bool = False,
    ) -> MusicProfile:
        text = prompt.strip()
        if not text:
            raise LLMError("Prompt must not be empty")

        client = self._create_client()
        try:
            profile = await client.chat.completions.create(
                model=resolve_openai_model(),
                response_model=MusicProfile,
                messages=build_messages(text),
                max_retries=LLM_MAX_RETRIES,
                temperature=0.2,
            )
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc

        return apply_request_hints(
            profile,
            track_count=track_count,
            instrumental_only=instrumental_only,
        )
