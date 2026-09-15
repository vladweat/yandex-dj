import { describe, expect, it } from "vitest";

import {
  parseExcludeArtists,
  SAMPLE_PROMPTS,
  validatePlaylistFormInput,
} from "@/features/playlist/playlist-form-utils";

describe("SAMPLE_PROMPTS", () => {
  it("covers kitchen / coding / synthwave golden prompts", () => {
    expect(SAMPLE_PROMPTS).toHaveLength(3);
    expect(SAMPLE_PROMPTS[0]).toContain("макароны");
    expect(SAMPLE_PROMPTS[1]).toContain("кодинг");
    expect(SAMPLE_PROMPTS[2]).toContain("синтвейв");
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
