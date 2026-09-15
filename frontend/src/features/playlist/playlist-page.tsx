"use client";

import { Panel } from "@/components/ui/card";
import { PlaylistForm } from "@/features/playlist/playlist-form";
import { PlaylistResult } from "@/features/playlist/playlist-result";

export function PlaylistPage() {
  return (
    <main className="flex-1 overflow-y-auto px-4 py-8 sm:px-6 sm:py-10">
      <div className="mx-auto max-w-3xl">
        <Panel
          title="Генерация плейлиста"
          subtitle="Промпт → Яндекс Музыка. Можно взять готовый пример ниже формы."
        >
          <PlaylistForm />
        </Panel>
        <PlaylistResult />
      </div>
    </main>
  );
}
