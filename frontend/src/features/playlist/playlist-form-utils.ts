import { ApiRequestError } from "@/lib/api";
import type {
  DiversityMode,
  PlaylistFormDraft,
  PlaylistGenerateResponse,
  PlaylistGenerationOptions,
  PlaylistHistoryItem,
} from "@/types/playlist";

export const SAMPLE_PROMPTS = [
  "под настроение пока варю макароны",
  "спокойная музыка для кодинга поздней ночью",
  "саундтрек для ночной поездки в стиле синтвейв",
] as const;

export function parseExcludeArtists(raw: string): string[] {
  return raw
    .split(/[,;\n]+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 20);
}

export function validatePlaylistFormInput(input: {
  prompt: string;
  trackCount: number;
}): string | null {
  const trimmed = input.prompt.trim();
  if (!trimmed) {
    return "Введите описание плейлиста";
  }
  if (trimmed.length > 2000) {
    return "Промпт не длиннее 2000 символов";
  }
  if (!Number.isFinite(input.trackCount) || input.trackCount < 1 || input.trackCount > 50) {
    return "Количество треков: от 1 до 50";
  }
  return null;
}

export function generationOptionsFromResult(current: {
  options?: PlaylistGenerationOptions | null;
  profile: { target_track_count: number; vocal_type: string };
}): PlaylistGenerationOptions {
  const opts = current.options;
  return {
    track_count: opts?.track_count ?? current.profile.target_track_count,
    instrumental_only:
      opts?.instrumental_only ?? current.profile.vocal_type === "instrumental_only",
    exclude_artists: opts?.exclude_artists ?? [],
    diversity: (opts?.diversity ?? "normal") as DiversityMode,
  };
}

export function draftFromHistoryItem(item: PlaylistHistoryItem): PlaylistFormDraft {
  const opts = item.options;
  return {
    prompt: item.prompt,
    trackCount: opts?.track_count ?? 25,
    instrumentalOnly: opts?.instrumental_only ?? false,
    excludeArtists: (opts?.exclude_artists ?? []).join(", "),
    diversity: opts?.diversity ?? "normal",
    sourceId: null,
  };
}

export type GenerateApiErrorAction =
  | { kind: "cancelled" }
  | { kind: "unauthorized" }
  | { kind: "validation"; message: string }
  | { kind: "unavailable" }
  | { kind: "timeout"; message: string }
  | { kind: "message"; message: string };

export function classifyGenerateApiError(err: unknown): GenerateApiErrorAction {
  if (!(err instanceof ApiRequestError)) {
    return { kind: "unavailable" };
  }
  if (err.status === 499) return { kind: "cancelled" };
  if (err.status === 401) return { kind: "unauthorized" };
  if (err.status === 422) return { kind: "validation", message: err.message };
  if (err.status === 504) return { kind: "timeout", message: err.message };
  if (err.status === 0 || err.status === 502 || err.status === 503) {
    return { kind: "unavailable" };
  }
  return { kind: "message", message: err.message };
}

export function pushGenerateWarnings(
  response: PlaylistGenerateResponse,
  pushToast: (message: string, variant?: "error" | "info") => void,
): void {
  for (const warning of response.warnings ?? []) {
    pushToast(warning, "info");
  }
}
