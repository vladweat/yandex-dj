from fastapi import Request

_ALLOWED = frozenset({"web", "telegram"})


def client_channel_from_request(request: Request) -> str:
    raw = request.headers.get("X-Client-Channel", "web").strip().lower()
    return raw if raw in _ALLOWED else "web"
