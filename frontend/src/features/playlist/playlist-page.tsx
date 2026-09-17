"use client";

import { Suspense, useEffect, useState } from "react";
import { History, X } from "lucide-react";
import { motion } from "framer-motion";

import { Button } from "@/components/ui/button";
import { PlaylistForm } from "@/features/playlist/playlist-form";
import { PlaylistHistory } from "@/features/playlist/playlist-history";
import { PlaylistResult } from "@/features/playlist/playlist-result";
import { usePlaylistStore } from "@/features/playlist/stores/playlist-store";
import { cn } from "@/lib/utils";

export function PlaylistPage() {
  const hasResult = usePlaylistStore((state) => Boolean(state.result));
  const [historyOpen, setHistoryOpen] = useState(false);

  useEffect(() => {
    if (!historyOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setHistoryOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [historyOpen]);

  return (
    <main className="relative flex min-h-0 flex-1 overflow-hidden">
      <div className="relative mx-auto flex min-h-0 w-full max-w-6xl flex-1">
        <section
          className={cn(
            "flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto px-4 sm:px-6",
            hasResult ? "justify-start py-5 sm:py-6" : "justify-center py-8 sm:py-10",
          )}
        >
          <div className="mb-3 flex justify-end lg:hidden">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setHistoryOpen(true)}
              aria-expanded={historyOpen}
            >
              <History />
              История
            </Button>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            className={cn("mx-auto w-full", hasResult ? "max-w-2xl" : "max-w-[34rem]")}
          >
            {!hasResult ? (
              <header className="mb-7 space-y-3 text-center sm:mb-8 sm:text-left">
                <p className="font-display text-[2rem] font-semibold leading-[1.1] tracking-tight text-foreground sm:text-[2.5rem]">
                  Prompt <span className="text-accent">DJ</span>
                </p>
                <p className="mx-auto max-w-md text-[15px] leading-relaxed text-muted-foreground sm:mx-0 sm:text-base">
                  Опишите настроение — плейлист сразу окажется в Яндекс Музыке
                </p>
              </header>
            ) : null}

            <Suspense fallback={<p className="text-sm text-muted-foreground">Загрузка…</p>}>
              <PlaylistForm variant="simple" compact={hasResult} />
            </Suspense>
            <PlaylistResult variant="simple" />
          </motion.div>
        </section>

        <aside className="hidden min-h-0 w-[19.5rem] shrink-0 border-l border-white/[0.06] bg-black/15 backdrop-blur-sm lg:flex lg:flex-col xl:w-[21rem]">
          <PlaylistHistory variant="simple" layout="rail" />
        </aside>
      </div>

      <div
        className={cn(
          "fixed inset-0 z-40 lg:hidden",
          historyOpen ? "pointer-events-auto" : "pointer-events-none",
        )}
      >
        <button
          type="button"
          aria-label="Закрыть историю"
          className={cn(
            "absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity",
            historyOpen ? "opacity-100" : "opacity-0",
          )}
          onClick={() => setHistoryOpen(false)}
        />
        <div
          className={cn(
            "absolute inset-y-0 right-0 flex w-[min(21rem,92vw)] flex-col border-l border-white/[0.08] bg-[#0c0f16] shadow-2xl transition-transform duration-300 ease-out",
            historyOpen ? "translate-x-0" : "translate-x-full",
          )}
          role="dialog"
          aria-modal="true"
          aria-label="История генераций"
        >
          <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
            <p className="font-display text-sm font-medium tracking-tight">История</p>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Закрыть"
              onClick={() => setHistoryOpen(false)}
            >
              <X />
            </Button>
          </div>
          <div className="min-h-0 flex-1">
            <PlaylistHistory
              variant="simple"
              layout="rail"
              onSelect={() => setHistoryOpen(false)}
            />
          </div>
        </div>
      </div>
    </main>
  );
}
