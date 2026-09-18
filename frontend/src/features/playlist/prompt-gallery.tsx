"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { GALLERY_PROMPTS, promptDeepLink } from "@/features/playlist/playlist-form-utils";

export function PromptGallery() {
  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <h2 className="font-display text-3xl font-semibold tracking-tight text-foreground">
          Галерея
        </h2>
        <p className="max-w-xl text-base leading-relaxed text-muted-foreground">
          Выберите ситуацию — откроется генерация с готовым промптом. Нужен вход через Яндекс.
        </p>
      </div>

      <ul className="grid gap-3 sm:grid-cols-2">
        {GALLERY_PROMPTS.map((item) => (
          <li
            key={item.prompt}
            className="group flex flex-col gap-3 rounded-2xl border border-white/10 bg-white/[0.03] p-5 transition hover:border-accent/30 hover:bg-white/[0.05]"
          >
            <div className="space-y-1.5">
              <h3 className="font-display text-sm font-medium tracking-tight text-foreground">
                {item.title}
              </h3>
              <p className="line-clamp-2 text-sm leading-relaxed text-muted-foreground">
                {item.prompt}
              </p>
            </div>
            <Button asChild variant="secondary" size="sm" className="mt-auto w-fit">
              <Link href={promptDeepLink(item.prompt, "", { utmSource: "gallery" })}>
                Собрать плейлист
              </Link>
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}
