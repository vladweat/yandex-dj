"""Сохранение состояния Device Flow между сессиями (разные ВМ / переключение интернета)."""

import json
from pathlib import Path
from typing import Any

PENDING_PATH = Path(__file__).resolve().parents[2] / ".auth" / "pending.json"


def save_pending(data: dict[str, Any]) -> Path:
    PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    PENDING_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return PENDING_PATH


def load_pending() -> dict[str, Any] | None:
    if not PENDING_PATH.exists():
        return None
    return json.loads(PENDING_PATH.read_text(encoding="utf-8"))


def merge_pending(data: dict[str, Any]) -> Path:
    current = load_pending() or {}
    current.update(data)
    return save_pending(current)


def clear_pending() -> None:
    if PENDING_PATH.exists():
        PENDING_PATH.unlink()


def has_offline_session(pending: dict[str, Any]) -> bool:
    """Токен и профиль в pending — запись в БД без запросов к Яндексу."""
    return bool(pending.get("access_token") and pending.get("yandex_uid") and pending.get("login"))
