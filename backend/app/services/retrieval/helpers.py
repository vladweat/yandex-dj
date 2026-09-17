import asyncio
import logging
from collections.abc import Awaitable

from yandex_music import Track

from app.schemas.llm import MusicProfile
from app.schemas.track import TrackCandidate
from app.utils.quality import is_spurious_track

logger = logging.getLogger(__name__)


def clean_count(candidates: list[TrackCandidate], profile: MusicProfile) -> int:
    return sum(1 for track in candidates if not is_spurious_track(track, profile))


async def gather_tracks(tasks: list[Awaitable[list[Track]]]) -> list[Track]:
    if not tasks:
        return []

    results = await asyncio.gather(*tasks, return_exceptions=True)
    tracks: list[Track] = []
    for result in results:
        if isinstance(result, Exception):
            logger.warning("Retrieval task failed: %s", result)
            continue
        tracks.extend(result)
    return tracks
