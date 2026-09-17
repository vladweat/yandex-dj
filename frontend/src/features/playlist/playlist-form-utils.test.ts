import { describe, expect, it } from "vitest";

import { ApiRequestError } from "@/lib/api";
import {
  classifyGenerateApiError,
  draftFromHistoryItem,
  generationOptionsFromResult,
  parseExcludeArtists,
  SAMPLE_PROMPTS,
  validatePlaylistFormInput,
} from "@/features/playlist/playlist-form-utils";

describe("SAMPLE_PROMPTS", () => {
  it("covers seven golden situational prompts", () => {
    expect(SAMPLE_PROMPTS).toHaveLength(7);
    expect(SAMPLE_PROMPTS[0]).toContain("макароны");
    expect(SAMPLE_PROMPTS[1]).toContain("кодинг");
    expect(SAMPLE_PROMPTS[2]).toContain("синтвейв");
    expect(SAMPLE_PROMPTS[3]).toContain("пробежки");
    expect(SAMPLE_PROMPTS[4]).toContain("уснуть");
    expect(SAMPLE_PROMPTS[5]).toContain("вечеринки");
    expect(SAMPLE_PROMPTS[6]).toContain("дождь");
  });
});

describe("GALLERY_PROMPTS", () => {
  it("includes golden samples plus extra situations", async () => {
    const { GALLERY_PROMPTS, promptDeepLink } = await import(
      "@/features/playlist/playlist-form-utils"
    );
    expect(GALLERY_PROMPTS.length).toBeGreaterThanOrEqual(10);
    expect(GALLERY_PROMPTS.slice(0, 7).map((item) => item.prompt)).toEqual([
      ...SAMPLE_PROMPTS,
    ]);
    expect(promptDeepLink("kitchen")).toBe("/?prompt=kitchen");
    expect(promptDeepLink("a b", "https://example.com")).toBe(
      "https://example.com/?prompt=a%20b",
    );
  });
});

describe("parseExcludeArtists", () => {
  it("splits commas and newlines, trims, caps at 20", () => {
    expect(parseExcludeArtists(" Kavinsky, Gunship ; Perturbator\nFM-84 ")).toEqual([
      "Kavinsky",
      "Gunship",
      "Perturbator",
      "FM-84",
    ]);
    const many = Array.from({ length: 25 }, (_, i) => `Artist${i}`).join(",");
    expect(parseExcludeArtists(many)).toHaveLength(20);
  });
});

describe("validatePlaylistFormInput", () => {
  it("requires a non-empty prompt", () => {
    expect(validatePlaylistFormInput({ prompt: "  ", trackCount: 25 })).toBe(
      "Введите описание плейлиста",
    );
  });

  it("limits prompt length", () => {
    expect(
      validatePlaylistFormInput({ prompt: "x".repeat(2001), trackCount: 25 }),
    ).toBe("Промпт не длиннее 2000 символов");
  });

  it("limits track count to 1..50", () => {
    expect(validatePlaylistFormInput({ prompt: "ok", trackCount: 0 })).toBe(
      "Количество треков: от 1 до 50",
    );
    expect(validatePlaylistFormInput({ prompt: "ok", trackCount: 51 })).toBe(
      "Количество треков: от 1 до 50",
    );
  });

  it("accepts valid input", () => {
    expect(validatePlaylistFormInput({ prompt: "dark synthwave", trackCount: 25 })).toBeNull();
  });
});

describe("generationOptionsFromResult", () => {
  it("prefers stored options over profile fallbacks", () => {
    const opts = generationOptionsFromResult({
      options: {
        track_count: 30,
        instrumental_only: true,
        exclude_artists: ["Kavinsky"],
        diversity: "high",
        use_library: true,
      },
      profile: { target_track_count: 25, vocal_type: "any" },
    });
    expect(opts).toEqual({
      track_count: 30,
      instrumental_only: true,
      exclude_artists: ["Kavinsky"],
      diversity: "high",
      use_library: true,
    });
  });

  it("falls back to profile when options missing", () => {
    const opts = generationOptionsFromResult({
      options: null,
      profile: { target_track_count: 20, vocal_type: "instrumental_only" },
    });
    expect(opts.track_count).toBe(20);
    expect(opts.instrumental_only).toBe(true);
    expect(opts.diversity).toBe("normal");
    expect(opts.use_library).toBe(false);
  });
});

describe("draftFromHistoryItem", () => {
  it("restores prompt and options for Повторить", () => {
    const draft = draftFromHistoryItem({
      id: "1",
      prompt: "kitchen vibe",
      title: "Kitchen",
      playlist_url: "https://example.com",
      options: {
        track_count: 15,
        instrumental_only: false,
        exclude_artists: ["A", "B"],
        diversity: "high",
        use_library: true,
      },
      created_at: "2026-09-15T00:00:00Z",
    });
    expect(draft).toEqual({
      prompt: "kitchen vibe",
      trackCount: 15,
      instrumentalOnly: false,
      excludeArtists: "A, B",
      diversity: "high",
      useLibrary: true,
      sourceId: null,
    });
  });
});

describe("classifyGenerateApiError", () => {
  it("maps common statuses", () => {
    expect(classifyGenerateApiError(new ApiRequestError("x", 499))).toEqual({
      kind: "cancelled",
    });
    expect(classifyGenerateApiError(new ApiRequestError("x", 401))).toEqual({
      kind: "unauthorized",
    });
    expect(classifyGenerateApiError(new ApiRequestError("bad", 422))).toEqual({
      kind: "validation",
      message: "bad",
    });
    expect(classifyGenerateApiError(new ApiRequestError("slow", 504))).toEqual({
      kind: "timeout",
      message: "slow",
    });
    expect(classifyGenerateApiError(new ApiRequestError("limit", 429))).toEqual({
      kind: "quota",
      message: "limit",
    });
    expect(classifyGenerateApiError(new ApiRequestError("down", 0))).toEqual({
      kind: "unavailable",
    });
    expect(classifyGenerateApiError(new Error("boom"))).toEqual({ kind: "unavailable" });
  });
});
