"""Validate Telegram Mini App initData (Web App)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from app.core.exceptions import AuthError

_MAX_INIT_DATA_AGE_SEC = 86400


def parse_telegram_user_id(init_data: str, *, bot_token: str) -> int:
    """Return Telegram user id from validated initData."""
    parsed = _validate_init_data(init_data, bot_token=bot_token)
    user_raw = parsed.get("user")
    if not user_raw:
        raise AuthError("Telegram initData has no user")
    try:
        user = json.loads(user_raw)
        user_id = user.get("id")
    except (json.JSONDecodeError, TypeError) as exc:
        raise AuthError("Invalid Telegram user payload") from exc
    if not isinstance(user_id, int):
        raise AuthError("Invalid Telegram user id")
    return user_id


def _validate_init_data(init_data: str, *, bot_token: str) -> dict[str, str]:
    raw = init_data.strip()
    if not raw:
        raise AuthError("Empty Telegram initData")

    pairs = parse_qsl(raw, keep_blank_values=True)
    parsed = dict(pairs)
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise AuthError("Telegram initData missing hash")

    auth_date_raw = parsed.get("auth_date")
    if auth_date_raw:
        try:
            auth_date = int(auth_date_raw)
        except ValueError as exc:
            raise AuthError("Invalid Telegram auth_date") from exc
        if time.time() - auth_date > _MAX_INIT_DATA_AGE_SEC:
            raise AuthError("Telegram initData expired")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if calculated != received_hash:
        raise AuthError("Invalid Telegram initData signature")

    return parsed
