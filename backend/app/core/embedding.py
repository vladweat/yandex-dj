"""Lazy loader для sentence-transformers (offline + online)."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
_model_warmed_up = False


def resolve_embedding_model_path() -> str:
    """Путь к локальной модели или HuggingFace id."""
    model_subdir = settings.embedding_model.replace("/", "--")

    if settings.embedding_model_path:
        base = Path(settings.embedding_model_path)
        nested = base / model_subdir
        if nested.is_dir() and any(nested.iterdir()):
            return str(nested)
        if base.is_dir() and any(base.iterdir()):
            return str(base)

    local = BACKEND_ROOT / ".models" / model_subdir
    if local.is_dir() and any(local.iterdir()):
        return str(local)

    return settings.embedding_model


def _configure_torch() -> None:
    try:
        import torch
    except ImportError:
        return

    threads = settings.scoring.torch_threads
    if threads > 0:
        torch.set_num_threads(threads)
    else:
        torch.set_num_threads(os.cpu_count() or 1)


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    from sentence_transformers import SentenceTransformer

    _configure_torch()
    model_path = resolve_embedding_model_path()
    logger.info("Loading embedding model from %s", model_path)
    return SentenceTransformer(model_path)


def warmup_embedding_model() -> None:
    """Прогрев модели при старте API — убирает cold start с первого запроса."""
    global _model_warmed_up
    if _model_warmed_up:
        return
    model = get_embedding_model()
    model.encode(
        ["query: warmup"],
        batch_size=1,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    _model_warmed_up = True
    logger.info("Embedding model warmed up")


def embedding_model_available() -> bool:
    try:
        get_embedding_model()
    except Exception as exc:
        logger.warning("Embedding model unavailable: %s", exc)
        return False
    return True
