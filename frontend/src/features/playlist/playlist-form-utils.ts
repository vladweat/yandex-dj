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
