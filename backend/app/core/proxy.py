"""Корпоративный прокси: NO_PROXY для внутренних сервисов, HTTPS_PROXY для внешних API.

Паттерн как в docwise: httpx/OpenAI читают env сами; yandex-music (aiohttp) — через proxy_url.
"""

from __future__ import annotations

import os

INTERNAL_HOSTS = (
    "localhost",
    "127.0.0.1",
    "postgres",
    "db",
    "redis",
)


def apply_internal_no_proxy() -> None:
    """Добавить Docker/internal-хосты в NO_PROXY, не затирая уже заданные значения."""
    for key in ("NO_PROXY", "no_proxy"):
        current = os.environ.get(key, "")
        parts: list[str] = []
        seen: set[str] = set()
        for item in [*current.split(","), *INTERNAL_HOSTS]:
            host = item.strip()
            if not host or host in seen:
                continue
            seen.add(host)
            parts.append(host)
        os.environ[key] = ",".join(parts)


def get_outbound_proxy_url() -> str | None:
    """Прокси для исходящих HTTPS-запросов (OAuth, API Яндекса, OpenAI)."""
    for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return None
