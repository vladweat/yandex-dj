import { create } from "zustand";

import type { PlaylistGenerateResponse } from "@/types/playlist";

interface PlaylistState {
  result: PlaylistGenerateResponse | null;
  setResult: (result: PlaylistGenerateResponse | null) => void;
  reset: () => void;
}

export const usePlaylistStore = create<PlaylistState>((set) => ({
  result: null,
  setResult: (result) => set({ result }),
  reset: () => set({ result: null }),
}));
