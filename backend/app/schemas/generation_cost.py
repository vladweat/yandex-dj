from typing import Any, Self

from pydantic import BaseModel, Field


class GenerationCostLLM(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    requests: int = 0


class GenerationCostYandex(BaseModel):
    api_calls: int = 0


class GenerationCostCover(BaseModel):
    image_requests: int = 0


class GenerationCost(BaseModel):
    """Persisted cost snapshot per playlist generation (C5)."""

    llm: GenerationCostLLM = Field(default_factory=GenerationCostLLM)
    yandex: GenerationCostYandex = Field(default_factory=GenerationCostYandex)
    cover: GenerationCostCover = Field(default_factory=GenerationCostCover)

    @classmethod
    def from_storage(cls, raw: dict[str, Any] | None) -> Self | None:
        if not raw or not isinstance(raw, dict):
            return None
        return cls.model_validate(raw)
