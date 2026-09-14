import type { QueryClient } from "@tanstack/react-query";

import { usePlaylistStore } from "@/features/playlist/stores/playlist-store";

/** Drop cached data and in-memory playlist state when the user identity changes. */
export function resetClientSessionState(queryClient: QueryClient) {
  queryClient.clear();
  usePlaylistStore.getState().reset();
}
