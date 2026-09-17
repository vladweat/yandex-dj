"""Нормализация и токенизация названий."""

import re

from app.utils.quality.patterns import TITLE_STOPWORDS


def compact(text: str) -> str:
    return re.sub(r"[^a-z0-9а-яё]", "", text.lower())


def tokenize_name(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def title_tokens(title: str) -> list[str]:
    normalized = re.sub(r"[\(\[].*?[\)\]]", "", title.lower())
    normalized = re.sub(r"[-–—/]", " ", normalized)
    tokens: list[str] = []
    for part in re.findall(r"[\w]+", normalized, flags=re.UNICODE):
        token = part.lower()
        if token and token not in TITLE_STOPWORDS:
            tokens.append(token)
    return tokens


def normalize_song_title(title: str) -> str:
    """Базовое название без суффиксов «- Artist», скобок и т.п."""
    normalized = title.lower().strip()
    normalized = re.sub(r"\s*[\(\[].*?[\)\]]", "", normalized)
    normalized = re.sub(r"\s+[-–—]\s+.+$", "", normalized)
    return normalized.strip()
