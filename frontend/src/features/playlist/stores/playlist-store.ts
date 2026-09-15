import { create } from "zustand";

import type { PlaylistFormDraft, PlaylistGenerateResponse } from "@/types/playlist";

interface PlaylistState {
  result: PlaylistGenerateResponse | null;
  draft: PlaylistFormDraft | null;
  setResult: (result: PlaylistGenerateResponse | null) => void;
  setDraft: (draft: PlaylistFormDraft | null) => void;
  reset: () => void;
}

export const usePlaylistStore = create<PlaylistState>((set) => ({
  result: null,
  draft: null,
  setResult: (result) => set({ result }),
  setDraft: (draft) => set({ draft }),
  reset: () => set({ result: null, draft: null }),
}));
