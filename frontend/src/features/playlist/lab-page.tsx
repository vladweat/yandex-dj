"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { History, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { PlaylistForm } from "@/features/playlist/playlist-form";
import { PlaylistHistory } from "@/features/playlist/playlist-history";
import { PlaylistResult } from "@/features/playlist/playlist-result";
import { cn } from "@/lib/utils";

export function LabPage() {
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
      <div className="relative mx-auto flex min-h-0 w-full max-w-7xl flex-1">
        <section className="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto px-4 py-5 sm:px-6 lg:pr-4">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
            <div>
              <h2 className="font-display text-xl font-semibold tracking-tight">Lab</h2>
              <p className="text-sm text-slate-400">
                Полный функционал. Пользовательский UI — на{" "}
                <Link href="/" className="text-slate-300 underline-offset-2 hover:underline">
                  главной
                </Link>
                .
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Link
                href="/debug"
                className="text-sm text-slate-400 underline-offset-2 hover:text-slate-200 hover:underline"
              >
                Яндекс account →
              </Link>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="lg:hidden"
                onClick={() => setHistoryOpen(true)}
              >
                <History />
                История
              </Button>
            </div>
          </div>

          <Panel
            title="Генерация (full)"
            subtitle="Все опции, MusicProfile, pool_stats, similarity. Обычно 7–20 сек."
          >
            <Suspense fallback={<p className="text-sm text-slate-400">Загрузка формы…</p>}>
              <PlaylistForm variant="full" />
            </Suspense>
          </Panel>

          <PlaylistResult variant="full" />
        </section>

        <aside className="hidden min-h-0 w-[min(22rem,30%)] shrink-0 border-l border-slate-800/80 lg:flex lg:flex-col">
          <PlaylistHistory variant="full" layout="rail" />
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
            "absolute inset-0 bg-black/50 transition-opacity",
            historyOpen ? "opacity-100" : "opacity-0",
          )}
          onClick={() => setHistoryOpen(false)}
        />
        <div
          className={cn(
            "absolute inset-y-0 right-0 flex w-[min(22rem,92vw)] flex-col border-l border-slate-800 bg-background shadow-xl transition-transform duration-200",
            historyOpen ? "translate-x-0" : "translate-x-full",
          )}
          role="dialog"
          aria-modal="true"
          aria-label="История"
        >
          <div className="flex items-center justify-between border-b border-slate-800 px-3 py-2">
            <p className="text-sm font-medium text-slate-200">История</p>
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
              variant="full"
              layout="rail"
              onSelect={() => setHistoryOpen(false)}
            />
          </div>
        </div>
      </div>
    </main>
  );
}
