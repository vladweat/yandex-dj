class AppError(Exception):
    """Базовая ошибка приложения."""


class SecurityError(AppError):
    """Ошибки шифрования."""


class AuthError(AppError):
    """Ошибки аутентификации (Device Flow, сессия)."""


class LLMError(AppError):
    """Ошибки LLM-парсинга."""


class RetrievalError(AppError):
    """Ошибки сбора кандидатов."""


class ScoringError(AppError):
    """Ошибки ранжирования."""


class ExportError(AppError):
    """Ошибки экспорта плейлиста."""


class YandexMusicError(AppError):
    """Ошибки API Яндекс Музыки."""


class NotFoundError(AppError):
    """Ресурс не найден или недоступен текущему пользователю."""


class PipelineTimeoutError(AppError):
    """Пайплайн генерации превысил PIPELINE_TIMEOUT_SEC."""


class CoverArtError(AppError):
    """Ошибки генерации AI-обложки."""


class QuotaExceededError(AppError):
    """Превышена soft-квота генераций за сутки."""

    def __init__(
        self,
        message: str,
        *,
        limit: int,
        used: int,
        remaining: int,
        resets_at: str,
    ) -> None:
        super().__init__(message)
        self.limit = limit
        self.used = used
        self.remaining = remaining
        self.resets_at = resets_at
