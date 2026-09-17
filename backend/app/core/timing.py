"""Общие хелперы для замеров latency в API и сервисах."""

import time


def elapsed_ms_since(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
