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
