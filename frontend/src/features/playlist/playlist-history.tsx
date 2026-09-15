"use client";

import { useQuery } from "@tanstack/react-query";
import { ExternalLink, RotateCcw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { ApiRequestError, clearSessionId, getPlaylist, listPlaylists } from "@/lib/api";
import { usePlaylistStore } from "@/features/playlist/stores/playlist-store";
import { useToastStore } from "@/stores/toast-store";
import { useRouter } from "next/navigation";

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat("ru-RU", {
      dateStyle: "short",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export function PlaylistHistory() {
  const router = useRouter();
  const setResult = usePlaylistStore((state) => state.setResult);
  const setDraft = usePlaylistStore((state) => state.setDraft);
  const pushToast = useToastStore((state) => state.push);
  const resultId = usePlaylistStore((state) => state.result?.id);

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["playlists", "history"],
    queryFn: () => listPlaylists(20, 0),
  });

  if (isError && error instanceof ApiRequestError && error.status === 401) {
    clearSessionId();
    router.replace("/login");
  }

  async function openItem(id: string) {
    try {
      const full = await getPlaylist(id);
      setResult(full);
    } catch (err) {
      if (err instanceof ApiRequestError) {
        pushToast(err.status === 0 ? "API недоступен" : err.message, "error");
        return;
      }
      pushToast("API недоступен", "error");
    }
  }

  function reusePrompt(prompt: string) {
    setDraft({
      prompt,
      trackCount: 25,
      instrumentalOnly: false,
      excludeArtists: "",
      diversity: "normal",
      sourceId: null,
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <Panel
      className="mt-8"
      title="История генераций"
      subtitle="Свои плейлисты из Prompt DJ. Клик — открыть результат; «повторить» — подставить промпт."
    >
      <div className="mb-3 flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          Обновить
        </Button>
        {resultId ? (
          <span className="text-xs text-slate-500">Показан результат: {resultId.slice(0, 8)}…</span>
        ) : null}
      </div>

      {isLoading ? <p className="text-sm text-slate-400">Загрузка…</p> : null}
      {isError ? (
        <p className="text-sm text-red-400">
          {error instanceof ApiRequestError && error.status === 0
            ? "API недоступен"
            : "Не удалось загрузить историю"}
        </p>
      ) : null}

      {!isLoading && !isError && data?.items.length === 0 ? (
        <p className="text-sm text-slate-400">Пока нет генераций — создайте первый плейлист выше.</p>
      ) : null}

      <ul className="space-y-3">
        {data?.items.map((item) => (
          <li
            key={item.id}
            className="rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-3"
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <button
                type="button"
                className="min-w-0 flex-1 text-left"
                onClick={() => openItem(item.id)}
              >
                <p className="font-medium text-slate-100">{item.title}</p>
                <p className="mt-1 line-clamp-2 text-sm text-slate-400">{item.prompt}</p>
                <p className="mt-1 text-xs text-slate-500">{formatDate(item.created_at)}</p>
              </button>
              <div className="flex flex-wrap gap-2">
                {item.pool_stats ? (
                  <Badge variant="outline">selected {item.pool_stats.selected}</Badge>
                ) : null}
                <Button type="button" size="sm" variant="outline" onClick={() => reusePrompt(item.prompt)}>
                  <RotateCcw />
                  Повторить
                </Button>
                <Button type="button" size="sm" variant="secondary" asChild>
                  <a href={item.playlist_url} target="_blank" rel="noopener noreferrer">
                    <ExternalLink />
                    Яндекс
                  </a>
                </Button>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
