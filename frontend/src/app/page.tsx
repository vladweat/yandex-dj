import type { Metadata } from "next";

import { AuthGate } from "@/features/auth/auth-gate";
import { PlaylistPage } from "@/features/playlist/playlist-page";

export const metadata: Metadata = {
  title: "Генерация — Prompt DJ",
};

export default function HomePage() {
  return (
    <AuthGate>
      <PlaylistPage />
    </AuthGate>
  );
}
