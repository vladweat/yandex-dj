"""OpenAI / KodikRouter client settings. Паттерн как в docwise."""

from app.core.config import Settings, settings

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_KODIK_BASE_URL = "https://api.kodikrouter.ru/v1"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_KODIK_MODEL = "openai/gpt-4o-mini"
KODIK_KEY_PREFIXES = ("sk-kr_", "kdk_", "sk-sr_")


def uses_kodik(cfg: Settings | None = None) -> bool:
    """KodikRouter: явный base URL или префикс API-ключа."""
    s = cfg or settings
    base = (s.openai_base_url or "").strip().lower()
    if "kodikrouter.ru" in base:
        return True
    key = (s.openai_api_key or "").strip()
    return key.startswith(KODIK_KEY_PREFIXES)


def resolve_openai_base_url(cfg: Settings | None = None) -> str:
    s = cfg or settings
    configured = (s.openai_base_url or "").strip().rstrip("/")
    if configured:
        return configured
    if uses_kodik(s):
        return DEFAULT_KODIK_BASE_URL
    return DEFAULT_OPENAI_BASE_URL


def resolve_openai_model(cfg: Settings | None = None) -> str:
    s = cfg or settings
    configured = (s.openai_model or "").strip()
    if configured:
        return configured
    if uses_kodik(s):
        return DEFAULT_KODIK_MODEL
    fallback = (s.llm_model or "").strip()
    return fallback or DEFAULT_OPENAI_MODEL


def openai_is_configured(cfg: Settings | None = None) -> bool:
    s = cfg or settings
    return bool((s.openai_api_key or "").strip())
