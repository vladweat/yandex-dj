"""Стабильный import path для RetrievalService (и monkeypatch settings в тестах)."""

from app.core.config import settings
from app.services.retrieval import RetrievalService, non_anchor_artists_from_ranked

__all__ = ["RetrievalService", "non_anchor_artists_from_ranked", "settings"]
