import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from app.core.exceptions import AuthError
from app.core.telegram_webapp import parse_telegram_user_id


def _sign_init_data(bot_token: str, fields: dict[str, str]) -> str:
    pairs = dict(fields)
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)


def test_parse_telegram_user_id_valid() -> None:
    token = "123456:ABC-DEF"
    user = json.dumps({"id": 424242, "first_name": "Test"})
    init_data = _sign_init_data(
        token,
        {"auth_date": str(int(time.time())), "user": user},
    )
    assert parse_telegram_user_id(init_data, bot_token=token) == 424242


def test_parse_telegram_user_id_bad_signature() -> None:
    init_data = "auth_date=1&user=%7B%22id%22%3A1%7D&hash=deadbeef"
    with pytest.raises(AuthError, match="signature"):
        parse_telegram_user_id(init_data, bot_token="token")
