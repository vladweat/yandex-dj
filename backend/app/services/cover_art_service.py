"""AI-обложка плейлиста (KodikRouter / Qwen Image 3 Pro) для шаринга в UI."""

from __future__ import annotations

import base64
import logging
import uuid
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.exceptions import CoverArtError
from app.core.llm_config import (
    openai_is_configured,
    resolve_openai_base_url,
    resolve_openai_image_model,
    uses_qwen_image_model,
)
from app.schemas.llm import MusicProfile

logger = logging.getLogger(__name__)

_IMAGE_PROMPT_MAX = 900
# Fallback для прямого OpenAI (dall-e-2), если модель не Qwen.
_DALLE2_SIZE = "512x512"


def build_cover_image_prompt(profile: MusicProfile, user_prompt: str) -> str:
    """Текст для image model: абстрактная обложка без текста и логотипов."""
    mood = ", ".join(profile.mood_tags[:6]) or "atmospheric"
    genres = ", ".join(profile.primary_genres[:5]) or "eclectic"
    activity = (profile.playlist_description or "").strip()
    if len(activity) > 160:
        activity = activity[:157] + "…"
    intent = user_prompt.strip()
    if len(intent) > 200:
        intent = intent[:197] + "…"
    parts = [
        f"Abstract square album cover art for a music playlist titled «{profile.playlist_title}».",
        f"Mood: {mood}. Genres: {genres}.",
    ]
    if activity:
        parts.append(f"Vibe: {activity}.")
    if intent:
        parts.append(f"Listener request: {intent}.")
    parts.append(
        "No text, no letters, no logos, no faces. Painterly, shareable, modern, high contrast."
    )
    prompt = " ".join(parts)
    if len(prompt) > _IMAGE_PROMPT_MAX:
        return prompt[: _IMAGE_PROMPT_MAX - 1] + "…"
    return prompt


def image_generate_kwargs(model: str, prompt: str) -> dict[str, Any]:
    """Параметры POST /v1/images/generations (OpenAI SDK + Kodik Qwen extras)."""
    kwargs: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "response_format": "b64_json",
        "n": 1,
    }
    if uses_qwen_image_model(model):
        kwargs["extra_body"] = {
            "aspect_ratio": settings.playlist_cover_aspect_ratio,
            "resolution": settings.playlist_cover_resolution,
        }
    else:
        kwargs["size"] = _DALLE2_SIZE
    return kwargs


class CoverArtService:
    def is_enabled(self) -> bool:
        return settings.playlist_cover_enabled and openai_is_configured()

    def storage_key_for(self, generation_id: uuid.UUID) -> str:
        return f"{generation_id}.png"

    def _storage_root(self) -> Path:
        root = Path(settings.cover_storage_dir)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def path_for_key(self, storage_key: str) -> Path | None:
        if not storage_key or "/" in storage_key or "\\" in storage_key or ".." in storage_key:
            return None
        return self._storage_root() / storage_key

    def read_bytes(self, storage_key: str | None) -> bytes | None:
        if not storage_key:
            return None
        path = self.path_for_key(storage_key)
        if path is None or not path.is_file():
            return None
        return path.read_bytes()

    async def generate(
        self,
        generation_id: uuid.UUID,
        profile: MusicProfile,
        user_prompt: str,
    ) -> str:
        if not self.is_enabled():
            raise CoverArtError("Cover art is disabled or OpenAI is not configured")

        prompt = build_cover_image_prompt(profile, user_prompt)
        model = resolve_openai_image_model()
        client = AsyncOpenAI(
            api_key=settings.openai_api_key.strip(),
            base_url=resolve_openai_base_url(),
        )
        try:
            response = await client.images.generate(
                **image_generate_kwargs(model, prompt),
            )
        except Exception as exc:
            logger.warning("Cover image API failed for %s: %s", generation_id, exc)
            raise CoverArtError("Image API request failed") from exc

        if not response.data or not response.data[0].b64_json:
            raise CoverArtError("Image API returned empty payload")

        try:
            raw = base64.b64decode(response.data[0].b64_json)
        except Exception as exc:
            raise CoverArtError("Invalid image payload") from exc

        storage_key = self.storage_key_for(generation_id)
        path = self._storage_root() / storage_key
        path.write_bytes(raw)
        return storage_key
