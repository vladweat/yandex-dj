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
from app.utils.quality import is_spurious_track
from app.utils.scoring import (
    build_prompt_text,
    candidates_for_embedding,
    cosine_scores,
    fallback_scores,
    merge_embedding_rank,
    select_playlist_tracks,
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
        ranked, method = await self.rank_pool(
            profile,
            candidates,
            user_prompt=user_prompt,
        )
        return self.select(ranked, profile), method

    async def rank_pool(
        self,
        profile: MusicProfile,
        candidates: list[TrackCandidate],
        *,
        user_prompt: str | None = None,
    ) -> tuple[list[tuple[TrackCandidate, float]], ScoringMethod]:
        """Полный ранжированный clean-пул (до diversity/cutoff)."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self._rank_pool_sync,
            profile,
            candidates,
            user_prompt,
        )

    @staticmethod
    def select(
        ranked: list[tuple[TrackCandidate, float]],
        profile: MusicProfile,
        *,
        diversity: str = "normal",
    ) -> list[ScoredTrack]:
        selected = select_playlist_tracks(ranked, profile, diversity=diversity)
        return [ScoredTrack.from_candidate(track, score) for track, score in selected]

    def _rank_pool_sync(
        self,
        profile: MusicProfile,
        candidates: list[TrackCandidate],
        user_prompt: str | None,
    ) -> tuple[list[tuple[TrackCandidate, float]], ScoringMethod]:
        filtered = [track for track in candidates if not is_spurious_track(track, profile)]
        if not filtered:
            filtered = candidates
        logger.info(
            "Scoring pool: raw=%d clean=%d target=%d",
            len(candidates),
            len(filtered),
            profile.target_track_count,
        )

        method: ScoringMethod = "embedding"
        embedded = self._embedding_rank(profile, filtered, user_prompt)
        if embedded is None:
            method = "fallback"
            ranked = fallback_scores(profile, filtered)
        else:
            ranked = merge_embedding_rank(profile, filtered, embedded)
        return ranked, method

    def _rank_sync(
        self,
        profile: MusicProfile,
        candidates: list[TrackCandidate],
        user_prompt: str | None,
    ) -> tuple[list[ScoredTrack], ScoringMethod]:
        ranked, method = self._rank_pool_sync(profile, candidates, user_prompt)
        return self.select(ranked, profile), method

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

        pool = candidates_for_embedding(
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
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked

    @staticmethod
    def elapsed_ms(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)
