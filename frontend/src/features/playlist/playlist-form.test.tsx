import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

import { PlaylistForm } from "@/features/playlist/playlist-form";
import { ONBOARDING_SITUATIONS, SAMPLE_PROMPTS } from "@/features/playlist/playlist-form-utils";
import { usePlaylistStore } from "@/features/playlist/stores/playlist-store";

const replace = vi.fn();
const generatePlaylist = vi.fn();
const fetchPlaylistQuota = vi.fn();
let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => searchParams,
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    generatePlaylist: (...args: unknown[]) => generatePlaylist(...args),
    fetchPlaylistQuota: (...args: unknown[]) => fetchPlaylistQuota(...args),
  };
});

function wrap(ui: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

afterEach(() => {
  cleanup();
  replace.mockClear();
  generatePlaylist.mockReset();
  fetchPlaylistQuota.mockReset();
  searchParams = new URLSearchParams();
  usePlaylistStore.getState().reset();
});

describe("PlaylistForm", () => {
  beforeEach(() => {
    fetchPlaylistQuota.mockResolvedValue({
      limit: 10,
      used: 2,
      remaining: 8,
      unlimited: false,
      resets_at: "2099-01-02T00:00:00+00:00",
    });
  });

  it("shows validation when submitting an empty prompt", async () => {
    wrap(<PlaylistForm />);
    fireEvent.click(screen.getByRole("button", { name: "Собрать плейлист" }));
    expect(await screen.findByText("Введите описание плейлиста")).toBeTruthy();
    expect(generatePlaylist).not.toHaveBeenCalled();
  });

  it("fills the prompt from a situation chip (simple)", () => {
    wrap(<PlaylistForm variant="simple" />);
    fireEvent.click(screen.getByRole("button", { name: ONBOARDING_SITUATIONS[0].title }));
    expect(screen.getByLabelText("Опишите плейлист")).toHaveProperty(
      "value",
      ONBOARDING_SITUATIONS[0].prompt,
    );
  });

  it("fills the prompt from a golden sample button (full)", () => {
    wrap(<PlaylistForm variant="full" />);
    fireEvent.click(screen.getByRole("button", { name: SAMPLE_PROMPTS[0] }));
    expect(screen.getByLabelText("Опишите плейлист")).toHaveProperty(
      "value",
      SAMPLE_PROMPTS[0],
    );
  });

  it("prefills prompt from ?prompt=", () => {
    searchParams = new URLSearchParams("prompt=night+drive");
    wrap(<PlaylistForm />);
    expect(screen.getByLabelText("Опишите плейлист")).toHaveProperty("value", "night drive");
  });

  it("submits a valid form to generatePlaylist", async () => {
    generatePlaylist.mockResolvedValue({
      id: "11111111-1111-1111-1111-111111111111",
      prompt: "dark synthwave",
      title: "Neon",
      description: "Night",
      playlist_url: "https://music.yandex.ru/users/u/playlists/1",
      tracks: [],
      pool_stats: { raw: 0, clean: 0, selected: 0 },
      profile: null,
    });

    wrap(<PlaylistForm />);
    fireEvent.change(screen.getByLabelText("Опишите плейлист"), {
      target: { value: "dark synthwave" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Собрать плейлист" }));

    await waitFor(() => {
      expect(generatePlaylist).toHaveBeenCalledWith(
        expect.objectContaining({
          prompt: "dark synthwave",
          track_count: 25,
          instrumental_only: false,
          diversity: "normal",
          use_library: false,
          source_id: null,
        }),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      );
    });
    expect(usePlaylistStore.getState().result?.title).toBe("Neon");
  });
});
