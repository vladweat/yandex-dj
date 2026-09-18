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
  "энергичная музыка для пробежки",
  "тихая музыка чтобы уснуть",
  "танцевальный плейлист для вечеринки дома",
  "грустная музыка под дождь у окна",
] as const;

/** Три ситуации для онбординга (P1.4). */
export const ONBOARDING_SITUATIONS = [
  { title: "Кухня", prompt: SAMPLE_PROMPTS[0] },
  { title: "Работа", prompt: SAMPLE_PROMPTS[1] },
  { title: "Дорога", prompt: SAMPLE_PROMPTS[2] },
] as const;

export type GalleryPrompt = {
  title: string;
  prompt: string;
};

/** Публичная галерея: 7 golden + доп. ситуации → /?prompt=… */
export const GALLERY_PROMPTS: GalleryPrompt[] = [
  { title: "Кухня", prompt: SAMPLE_PROMPTS[0] },
  { title: "Кодинг", prompt: SAMPLE_PROMPTS[1] },
  { title: "Синтвейв", prompt: SAMPLE_PROMPTS[2] },
  { title: "Пробежка", prompt: SAMPLE_PROMPTS[3] },
  { title: "Сон", prompt: SAMPLE_PROMPTS[4] },
  { title: "Вечеринка", prompt: SAMPLE_PROMPTS[5] },
  { title: "Дождь", prompt: SAMPLE_PROMPTS[6] },
  { title: "Утро", prompt: "лёгкая музыка на утро с кофе у окна" },
  { title: "Поезд", prompt: "меланхоличный плейлист для долгой поездки в поезде" },
  { title: "Фокус", prompt: "глубокий фокус без слов для работы за ноутбуком" },
  { title: "Вечер", prompt: "мягкий вечерний джаз для ужина вдвоём" },
];

export type ShareLinkSource = "gallery" | "result" | "copy";

const SHARE_UTM = {
  medium: "prompt",
  campaign: "prompt_dj",
} as const;

/** Ожидание latency для UX (P2.5); согласовано с PRODUCT guardrail ~7–12 сек. */
export const GENERATION_LATENCY_HINT = "~12 сек";
export const REGEN_LATENCY_HINT = "«Ещё вариант» — без LLM, обычно быстрее";

export function promptDeepLink(
  prompt: string,
  origin = "",
  options?: { utmSource?: ShareLinkSource },
): string {
  const params = new URLSearchParams();
  params.set("prompt", prompt);
  params.set("utm_source", options?.utmSource ?? "share");
  params.set("utm_medium", SHARE_UTM.medium);
  params.set("utm_campaign", SHARE_UTM.campaign);
  const path = `/?${params.toString()}`;
  return origin ? `${origin}${path}` : path;
}

/** Текст для шаринга: промпт + deep link с UTMs (P2.3). */
export function formatPromptShareText(prompt: string, url: string): string {
  const trimmed = prompt.trim();
  return trimmed ? `${trimmed}\n\n${url}` : url;
}

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
    use_library: opts?.use_library ?? false,
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
    useLibrary: opts?.use_library ?? false,
    sourceId: null,
  };
}

export type GenerateApiErrorAction =
  | { kind: "cancelled" }
  | { kind: "unauthorized" }
  | { kind: "validation"; message: string }
  | { kind: "unavailable" }
  | { kind: "timeout"; message: string }
  | { kind: "quota"; message: string }
  | { kind: "message"; message: string };

export function classifyGenerateApiError(err: unknown): GenerateApiErrorAction {
  if (!(err instanceof ApiRequestError)) {
    return { kind: "unavailable" };
  }
  if (err.status === 499) return { kind: "cancelled" };
  if (err.status === 401) return { kind: "unauthorized" };
  if (err.status === 422) return { kind: "validation", message: err.message };
  if (err.status === 429) return { kind: "quota", message: err.message };
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
