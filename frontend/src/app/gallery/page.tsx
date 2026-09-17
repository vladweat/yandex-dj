import type { Metadata } from "next";

import { PromptGallery } from "@/features/playlist/prompt-gallery";

export const metadata: Metadata = {
  title: "Галерея промптов — Prompt DJ",
  description: "Готовые ситуации для генерации плейлиста в Яндекс Музыке",
};

export default function GalleryPage() {
  return (
    <main className="flex-1 overflow-y-auto px-4 py-8 sm:px-6">
      <div className="mx-auto max-w-3xl">
        <PromptGallery />
      </div>
    </main>
  );
}
