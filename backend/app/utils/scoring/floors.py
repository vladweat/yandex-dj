"""Пороги score: elbow, медиана топ-K, playlist fill."""

from __future__ import annotations

import numpy as np
from app.schemas.track import TrackCandidate
from app.utils.scoring.constants import ELBOW_MIN_GAP, TOP_MEDIAN_MAX_GAP, TOP_MEDIAN_WINDOW


def score_window(scores: list[float], limit: int) -> list[float]:
    window_size = min(len(scores), max(limit * 2, 10))
    return scores[:window_size]


def largest_score_gap_cut(window: list[float]) -> tuple[float, int]:
    """Наибольший разрыв между соседними score; cut_index — первый индекс после разрыва."""
    if len(window) < 2:
        return 0.0, len(window) - 1
    best_gap = 0.0
    cut_index = len(window) - 1
    for index in range(len(window) - 1):
        gap = window[index] - window[index + 1]
        if gap > best_gap:
            best_gap = gap
            cut_index = index + 1
    return best_gap, cut_index


def adaptive_score_floor(scores: list[float], limit: int) -> float:
    """
    Порог по наибольшему разрыву в ранжированном списке (elbow).
    Не зависит от жанра; fallback — мягкий ratio от топа.
    """
    if not scores:
        return 0.0
    if len(scores) == 1:
        return scores[0] - 1e-6

    window = score_window(scores, limit)
    best_gap, cut_index = largest_score_gap_cut(window)

    if len(scores) < limit:
        return scores[-1] - 1e-6

    min_tracks = max(1, limit // 2)
    if best_gap >= ELBOW_MIN_GAP and cut_index >= min_tracks:
        return window[cut_index] - 1e-6

    return max(window[-1] - 1e-6, window[0] * 0.82)


def playlist_score_floor(scores: list[float], limit: int, *, strict: bool) -> float:
    if not scores:
        return 0.0
    elbow = adaptive_score_floor(scores, limit)
    if strict or len(scores) < limit:
        return elbow
    fill_floor = scores[limit - 1] - 1e-6
    return min(elbow, fill_floor)


def filter_by_top_median_gap(
    ranked: list[tuple[TrackCandidate, float]],
    *,
    window: int = TOP_MEDIAN_WINDOW,
    max_gap: float = TOP_MEDIAN_MAX_GAP,
) -> list[tuple[TrackCandidate, float]]:
    """
    Убирает embedding false positives в хвосте: score << медианы топ-K.

    Не привязан к жанру/промпту. На маленьких пулах (< window) не режет.
    """
    if len(ranked) < window:
        return ranked
    top_scores = [score for _, score in ranked[:window]]
    median = float(np.median(np.asarray(top_scores, dtype=np.float64)))
    floor = median - max_gap
    return [(track, score) for track, score in ranked if score >= floor]
