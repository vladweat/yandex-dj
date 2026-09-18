"""Per-request counters for generation cost (LLM tokens, Yandex API calls)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any


@dataclass
class GenerationUsageAcc:
    llm_prompt_tokens: int = 0
    llm_completion_tokens: int = 0
    llm_requests: int = 0
    yandex_api_calls: int = 0
    cover_image_requests: int = 0

    def add_llm_usage(self, *, prompt_tokens: int, completion_tokens: int) -> None:
        self.llm_prompt_tokens += max(0, prompt_tokens)
        self.llm_completion_tokens += max(0, completion_tokens)
        self.llm_requests += 1

    def record_yandex_api_call(self, count: int = 1) -> None:
        if count > 0:
            self.yandex_api_calls += count

    def record_cover_image_request(self) -> None:
        self.cover_image_requests += 1

    def to_storage(self) -> dict[str, Any]:
        total = self.llm_prompt_tokens + self.llm_completion_tokens
        return {
            "llm": {
                "prompt_tokens": self.llm_prompt_tokens,
                "completion_tokens": self.llm_completion_tokens,
                "total_tokens": total,
                "requests": self.llm_requests,
            },
            "yandex": {"api_calls": self.yandex_api_calls},
            "cover": {"image_requests": self.cover_image_requests},
        }


_generation_usage: ContextVar[GenerationUsageAcc | None] = ContextVar(
    "generation_usage",
    default=None,
)


def begin_generation_usage() -> tuple[GenerationUsageAcc, Token]:
    acc = GenerationUsageAcc()
    token = _generation_usage.set(acc)
    return acc, token


def reset_generation_usage(token: Token) -> None:
    _generation_usage.reset(token)


@contextmanager
def generation_usage_scope() -> Iterator[GenerationUsageAcc]:
    acc, token = begin_generation_usage()
    try:
        yield acc
    finally:
        reset_generation_usage(token)


def current_generation_usage() -> GenerationUsageAcc | None:
    return _generation_usage.get()


def record_yandex_api_call(count: int = 1) -> None:
    acc = _generation_usage.get()
    if acc is not None:
        acc.record_yandex_api_call(count)


def token_usage_from_completion(completion: Any) -> tuple[int, int]:
    usage = getattr(completion, "usage", None)
    if usage is None:
        return 0, 0
    if isinstance(usage, dict):
        prompt = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        return prompt, completion_tokens
    prompt = int(getattr(usage, "prompt_tokens", None) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", None) or 0)
    return prompt, completion_tokens
