"""C5: generation cost counters."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from app.core.generation_usage import (
    GenerationUsageAcc,
    generation_usage_scope,
    token_usage_from_completion,
)
from app.services.yandex.base import YandexApiBase


def test_token_usage_from_completion_object() -> None:
    completion = MagicMock()
    completion.usage = MagicMock(prompt_tokens=100, completion_tokens=40)
    assert token_usage_from_completion(completion) == (100, 40)


def test_generation_usage_scope_resets_context() -> None:
    with generation_usage_scope() as acc:
        acc.record_yandex_api_call(3)
        assert acc.yandex_api_calls == 3
    with generation_usage_scope() as acc2:
        assert acc2.yandex_api_calls == 0


@pytest.mark.asyncio
async def test_throttle_records_yandex_call() -> None:
    class Stub(YandexApiBase):
        pass

    stub = Stub()
    with generation_usage_scope() as acc:
        await stub._throttle()
    assert acc.yandex_api_calls == 1


def test_to_storage_shape() -> None:
    acc = GenerationUsageAcc()
    acc.add_llm_usage(prompt_tokens=10, completion_tokens=5)
    acc.record_yandex_api_call(7)
    acc.record_cover_image_request()
    stored = acc.to_storage()
    assert stored["llm"]["total_tokens"] == 15
    assert stored["yandex"]["api_calls"] == 7
    assert stored["cover"]["image_requests"] == 1
