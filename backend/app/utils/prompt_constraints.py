"""Извлечение ограничений из NL-промпта (diversity, язык) и hard-якорей."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.schemas.llm import MusicProfile

_CYRILLIC = re.compile(r"[а-яёА-ЯЁ]")

_DIVERSITY_HINT = re.compile(
    r"разнообразн|поразнообраз|diverse|more variety|variety\b",
    re.IGNORECASE,
)

_EXCLUDE_RU = re.compile(
    r"("
    r"исключ\w*\s+русск|"
    r"без\s+русск|"
    r"не\s+русск|"
    r"только\s+(?:англ|american|english)|"
    r"no\s+russian|"
    r"exclude\s+russian|"
    r"english\s+only"
    r")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PromptConstraints:
    prefer_high_diversity: bool = False
    exclude_languages: list[str] = field(default_factory=list)


def extract_prompt_constraints(prompt: str) -> PromptConstraints:
    text = prompt.strip()
    exclude: list[str] = []
    if _EXCLUDE_RU.search(text):
        exclude.append("ru")
    return PromptConstraints(
        prefer_high_diversity=bool(_DIVERSITY_HINT.search(text)),
        exclude_languages=exclude,
    )


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9а-яё]", "", text.lower())


def artists_mentioned_in_prompt(prompt: str, artists: list[str]) -> list[str]:
    """Явные совпадения имени артиста в промпте (латиница/кириллица as-is)."""
    compact_prompt = _compact(prompt)
    prompt_lower = prompt.lower()
    mentioned: list[str] = []
    for artist in artists:
        name = artist.strip()
        if not name:
            continue
        compact = _compact(name)
        if len(compact) >= 4 and compact in compact_prompt:
            mentioned.append(name)
            continue
        if name.lower() in prompt_lower:
            mentioned.append(name)
    return mentioned


def resolve_hard_reference_artists(
    profile: MusicProfile,
    prompt: str | None = None,
) -> list[str]:
    """
    Hard-якоря: boost + elevated diversity slots.
    Soft (остальные reference_artists) — только retrieval.
    """
    refs = [name.strip() for name in profile.reference_artists if name.strip()]
    if not refs:
        return []

    declared = [name.strip() for name in profile.hard_reference_artists if name.strip()]
    # Только пересечение с reference_artists (порядок declared).
    ref_by_compact = {_compact(name): name for name in refs}
    hard: list[str] = []
    seen: set[str] = set()
    for name in declared:
        key = _compact(name)
        matched = ref_by_compact.get(key)
        if matched is None:
            for ref in refs:
                if artist_name_matches(name, ref):
                    matched = ref
                    break
        if matched and matched not in seen:
            hard.append(matched)
            seen.add(matched)
        if len(hard) >= 3:
            return hard

    if hard:
        return hard

    if prompt and prompt.strip():
        for name in artists_mentioned_in_prompt(prompt, refs):
            if name not in seen:
                hard.append(name)
                seen.add(name)
            if len(hard) >= 3:
                return hard
        if hard:
            return hard

    # Cold-start без имён в промпте: топ-2 из LLM-якорей.
    return refs[:2]


def artist_name_matches(left: str, right: str) -> bool:
    return _compact(left) == _compact(right)


def ensure_hard_reference_artists(
    profile: MusicProfile,
    prompt: str | None = None,
) -> MusicProfile:
    hard = resolve_hard_reference_artists(profile, prompt)
    if hard == list(profile.hard_reference_artists):
        return profile
    return profile.model_copy(update={"hard_reference_artists": hard})


def track_matches_excluded_language(track_title: str, artists: list[str], lang: str) -> bool:
    if lang != "ru":
        return False
    haystack = f"{track_title} {' '.join(artists)}"
    return bool(_CYRILLIC.search(haystack))


def filter_excluded_languages(
    tracks: list,
    exclude_languages: list[str],
) -> list:
    """Убрать треки с признаками исключённого языка (сейчас: ru = кириллица)."""
    langs = [lang.lower().strip() for lang in exclude_languages if lang.strip()]
    if not langs:
        return tracks
    kept = []
    for track in tracks:
        title = getattr(track, "title", "") or ""
        artists = list(getattr(track, "artists", []) or [])
        if any(track_matches_excluded_language(title, artists, lang) for lang in langs):
            continue
        kept.append(track)
    return kept
