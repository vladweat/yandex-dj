"""Векторное ранжирование треков (sentence-transformers)."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Literal

import numpy as np

from app.core.config import settings
from app.core.embedding import get_embedding_model
from app.schemas.llm import MusicProfile
from app.schemas.scoring import ScoredTrack
from app.schemas.track import TrackCandidate
from app.utils.scoring import (
    apply_diversity_filter,
    apply_reference_artist_boost,
    build_prompt_text,
    cosine_scores,
    fallback_scores,
    max_tracks_per_artist,
    merge_embedding_rank,
    select_embedding_pool,
)

logger = logging.getLogger(__name__)

ScoringMethod = Literal["embedding", "fallback"]


class ScoringService:
    async def rank(
        self,
        profile: MusicProfile,
        candidates: list[TrackCandidate],
        *,
        user_prompt: str | None = None,
    ) -> tuple[list[ScoredTrack], ScoringMethod]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self._rank_sync,
            profile,
            candidates,
            user_prompt,
        )

    def _rank_sync(
        self,
        profile: MusicProfile,
        candidates: list[TrackCandidate],
        user_prompt: str | None,
    ) -> tuple[list[ScoredTrack], ScoringMethod]:
        limit = profile.target_track_count
        max_per_artist = max_tracks_per_artist(limit)

        method: ScoringMethod = "embedding"
        embedded = self._embedding_rank(profile, candidates, user_prompt)
        if embedded is None:
            method = "fallback"
            ranked = fallback_scores(profile, candidates)
        else:
            ranked = merge_embedding_rank(profile, candidates, embedded)

        filtered = apply_diversity_filter(
            ranked,
            limit=limit,
            max_per_artist=max_per_artist,
        )
        tracks = [ScoredTrack.from_candidate(track, score) for track, score in filtered]
        return tracks, method

    def _embedding_rank(
        self,
        profile: MusicProfile,
        candidates: list[TrackCandidate],
        user_prompt: str | None,
    ) -> list[tuple[TrackCandidate, float]] | None:
        try:
            model = get_embedding_model()
        except Exception as exc:
            logger.warning("Embedding model load failed, using fallback: %s", exc)
            return None

        pool = select_embedding_pool(
            profile,
            candidates,
            limit=settings.scoring_embed_limit,
        )
        prompt_text = build_prompt_text(profile, user_prompt)
        query = f"query: {prompt_text}"
        passages = [f"passage: {track.embedding_passport()}" for track in pool]

        try:
            embeddings = model.encode(
                [query, *passages],
                batch_size=settings.embedding_batch_size,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
        except Exception as exc:
            logger.warning("Embedding encode failed, using fallback: %s", exc)
            return None

        query_vec = np.asarray(embeddings[0])
        doc_vecs = np.asarray(embeddings[1:])
        scores = cosine_scores(query_vec, doc_vecs)

        ranked = list(zip(pool, scores.tolist(), strict=True))
        ranked = apply_reference_artist_boost(profile, ranked)
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked

    @staticmethod
    def elapsed_ms(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)
