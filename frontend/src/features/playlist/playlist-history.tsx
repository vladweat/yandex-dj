"use client";

import { useQuery } from "@tanstack/react-query";
import { ExternalLink, RotateCcw } from "lucide-react";
import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { ApiRequestError, clearSessionId, getPlaylist, listPlaylists } from "@/lib/api";
import { usePlaylistStore } from "@/features/playlist/stores/playlist-store";
import { useToastStore } from "@/stores/toast-store";
import { draftFromHistoryItem } from "@/features/playlist/playlist-form-utils";
import type { PlaylistHistoryItem } from "@/types/playlist";
import { cn } from "@/lib/utils";

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

export type PlaylistHistoryVariant = "simple" | "full";
export type PlaylistHistoryLayout = "stack" | "rail";

type PlaylistHistoryProps = {
  variant?: PlaylistHistoryVariant;
  layout?: PlaylistHistoryLayout;
  onSelect?: () => void;
};

export function PlaylistHistory({
  variant = "simple",
  layout = "stack",
  onSelect,
}: PlaylistHistoryProps) {
  const router = useRouter();
  const setResult = usePlaylistStore((state) => state.setResult);
  const setDraft = usePlaylistStore((state) => state.setDraft);
  const pushToast = useToastStore((state) => state.push);
  const resultId = usePlaylistStore((state) => state.result?.id);
  const isFull = variant === "full";
  const isRail = layout === "rail";

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
      onSelect?.();
    } catch (err) {
      if (err instanceof ApiRequestError) {
        pushToast(err.status === 0 ? "API недоступен" : err.message, "error");
        return;
      }
      pushToast("API недоступен", "error");
    }
  }

  function reusePrompt(item: PlaylistHistoryItem) {
    setDraft(draftFromHistoryItem(item));
    onSelect?.();
  }

  const list = (
    <>
      {isFull && !isRail ? (
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
            <span className="text-xs text-muted-foreground">
              Показан результат: {resultId.slice(0, 8)}…
            </span>
          ) : null}
        </div>
      ) : null}

      {isLoading ? <p className="text-sm text-muted-foreground">Загрузка…</p> : null}
      {isError ? (
        <p className="text-sm text-red-400">
          {error instanceof ApiRequestError && error.status === 0
            ? "API недоступен"
            : "Не удалось загрузить историю"}
        </p>
      ) : null}

      {!isLoading && !isError && data?.items.length === 0 ? (
        <p className="px-1 text-sm text-muted-foreground">
          {isRail ? "Здесь появятся ваши плейлисты" : "Пока пусто — соберите первый плейлист выше."}
        </p>
      ) : null}

      <ul className={cn(isRail ? "space-y-1" : "space-y-3")}>
        {data?.items.map((item) => (
          <li key={item.id}>
            {isRail ? (
              <div
                className={cn(
                  "group rounded-xl px-2.5 py-2.5 transition-colors",
                  resultId === item.id
                    ? "bg-accent/10"
                    : "hover:bg-white/[0.04]",
                )}
              >
                <button
                  type="button"
                  className="w-full text-left"
                  onClick={() => void openItem(item.id)}
                >
                  <p className="line-clamp-1 text-[13px] font-semibold tracking-tight text-foreground">
                    {item.title}
                  </p>
                  <p className="mt-0.5 line-clamp-1 text-[12px] text-muted-foreground">
                    {item.prompt}
                  </p>
                  <p className="mt-1 text-[11px] tabular-nums text-muted-foreground/70">
                    {formatDate(item.created_at)}
                  </p>
                </button>
                <div className="mt-2 flex gap-1.5 opacity-80 transition-opacity group-hover:opacity-100">
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-7 flex-1 justify-start px-2 text-[12px]"
                    onClick={() => reusePrompt(item)}
                  >
                    <RotateCcw className="size-3.5" />
                    Снова
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-7 flex-1 justify-start px-2 text-[12px]"
                    asChild
                  >
                    <a href={item.playlist_url} target="_blank" rel="noopener noreferrer">
                      <ExternalLink className="size-3.5" />
                      Яндекс
                    </a>
                  </Button>
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-white/10 bg-white/[0.02] px-3 py-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <button
                    type="button"
                    className="min-w-0 flex-1 text-left"
                    onClick={() => void openItem(item.id)}
                  >
                    <p className="font-medium text-foreground">{item.title}</p>
                    <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{item.prompt}</p>
                    <p className="mt-1 text-xs text-muted-foreground/70">
                      {formatDate(item.created_at)}
                    </p>
                  </button>
                  <div className="flex flex-wrap gap-1.5">
                    {isFull && item.pool_stats ? (
                      <Badge variant="outline">selected {item.pool_stats.selected}</Badge>
                    ) : null}
                    <Button type="button" size="sm" variant="outline" onClick={() => reusePrompt(item)}>
                      <RotateCcw />
                      {isFull ? "Повторить" : "Снова"}
                    </Button>
                    <Button type="button" size="sm" variant="secondary" asChild>
                      <a href={item.playlist_url} target="_blank" rel="noopener noreferrer">
                        <ExternalLink />
                        Яндекс
                      </a>
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </>
  );

  if (isRail) {
    return (
      <div className="flex h-full min-h-0 flex-col">
        <div className="flex shrink-0 items-center justify-between gap-2 px-4 pb-2 pt-5">
          <p className="font-display text-[13px] font-medium tracking-wide text-muted-foreground uppercase">
            История
          </p>
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            className="text-[12px] font-medium text-muted-foreground transition hover:text-foreground disabled:opacity-50"
          >
            Обновить
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">{list}</div>
      </div>
    );
  }

  return (
    <Panel
      className="mt-8"
      title="История"
      subtitle={
        isFull
          ? "Клик — открыть результат; «повторить» — подставить промпт и опции."
          : "Ваши плейлисты. Нажмите, чтобы открыть снова."
      }
    >
      {list}
    </Panel>
  );
}
