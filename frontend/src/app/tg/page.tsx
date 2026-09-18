import { AuthGate } from "@/features/auth/auth-gate";
import { PlaylistPage } from "@/features/playlist/playlist-page";

export default function TelegramPlaylistPage() {
  return (
    <AuthGate>
      <PlaylistPage />
    </AuthGate>
  );
}
