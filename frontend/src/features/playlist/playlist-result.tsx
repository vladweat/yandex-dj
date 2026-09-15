"use client";

import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Copy, ExternalLink, Loader2, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { clearSessionId, generatePlaylist } from "@/lib/api";
import {
  classifyGenerateApiError,
  generationOptionsFromResult,
  pushGenerateWarnings,
} from "@/features/playlist/playlist-form-utils";
import { usePlaylistStore } from "@/features/playlist/stores/playlist-store";
import { useToastStore } from "@/stores/toast-store";
import { useRouter } from "next/navigation";

function formatDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${min}:${sec.toString().padStart(2, "0")}`;
}

function formatScore(score: number): string {
  return score.toFixed(3);
}

export function PlaylistResult() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const result = usePlaylistStore((state) => state.result);
  const setResult = usePlaylistStore((state) => state.setResult);
  const pushToast = useToastStore((state) => state.push);
  const [regenLoading, setRegenLoading] = useState(false);
  const [copyDone, setCopyDone] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  if (!result) return null;

  const current = result;
  const stats = current.pool_stats;
  const profile = current.profile;

  async function handleCopy() {
    const text = `${current.playlist_url}\n\n${current.prompt}`;
    try {
      await navigator.clipboard.writeText(text);
      setCopyDone(true);
      pushToast("Ссылка и промпт скопированы", "info");
      window.setTimeout(() => setCopyDone(false), 2000);
    } catch {
      pushToast("Не удалось скопировать", "error");
    }
  }

  async function handleAnotherVariant() {
    setRegenLoading(true);
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const opts = generationOptionsFromResult(current);
    try {
      const response = await generatePlaylist(
        {
          prompt: current.prompt,
          track_count: opts.track_count,
          instrumental_only: opts.instrumental_only,
          exclude_artists: opts.exclude_artists,
          diversity: opts.diversity,
          source_id: current.id,
        },
        { signal: controller.signal },
      );
      setResult(response);
      pushGenerateWarnings(response, pushToast);
      void queryClient.invalidateQueries({ queryKey: ["playlists", "history"] });
    } catch (err) {
      const action = classifyGenerateApiError(err);
      if (action.kind === "cancelled") {
        pushToast("Генерация отменена", "info");
      } else if (action.kind === "unauthorized") {
        clearSessionId();
        pushToast("Сессия истекла — войдите снова", "error");
        router.replace("/login");
      } else if (action.kind === "timeout" || action.kind === "message") {
        pushToast(action.message, "error");
      } else if (action.kind === "unavailable") {
        pushToast("API недоступен", "error");
      }
    } finally {
      setRegenLoading(false);
      abortRef.current = null;
    }
  }

  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle>{current.title}</CardTitle>
        <CardDescription className="whitespace-pre-wrap">{current.description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Button asChild>
            <a href={current.playlist_url} target="_blank" rel="noopener noreferrer">
              Открыть в Яндекс Музыке
              <ExternalLink />
            </a>
          </Button>
          <Button type="button" variant="secondary" onClick={handleCopy}>
            <Copy />
            {copyDone ? "Скопировано" : "Копировать ссылку и промпт"}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={handleAnotherVariant}
            disabled={regenLoading}
          >
            {regenLoading ? <Loader2 className="animate-spin" /> : <RefreshCw />}
            Ещё вариант
          </Button>
          {regenLoading ? (
            <Button
              type="button"
              variant="ghost"
              onClick={() => abortRef.current?.abort()}
            >
              Отменить
            </Button>
          ) : null}
          <Badge variant="secondary">{current.tracks.length} треков</Badge>
          {stats ? (
            <>
              <Badge variant="outline">raw {stats.raw}</Badge>
              <Badge variant="outline">clean {stats.clean}</Badge>
              <Badge variant="outline">selected {stats.selected}</Badge>
            </>
          ) : null}
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3 text-sm">
          <p className="mb-2 font-medium text-slate-200">Музыкальный профиль</p>
          <dl className="grid gap-2 sm:grid-cols-2">
            <div>
              <dt className="text-xs text-slate-500">Жанры</dt>
              <dd className="text-slate-300">{profile.primary_genres.join(", ") || "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Настроение</dt>
              <dd className="text-slate-300">{profile.mood_tags.join(", ") || "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Вокал</dt>
              <dd className="text-slate-300">{profile.vocal_type}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Референсы</dt>
              <dd className="text-slate-300">{profile.reference_artists.join(", ")}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-xs text-slate-500">Поисковые запросы</dt>
              <dd className="text-slate-300">{profile.search_queries.join(" · ")}</dd>
            </div>
          </dl>
        </div>

        <div className="overflow-x-auto rounded-lg border border-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-800 bg-slate-950/60 text-slate-400">
              <tr>
                <th className="w-10 px-3 py-2 font-medium">#</th>
                <th className="px-3 py-2 font-medium">Трек</th>
                <th className="px-3 py-2 font-medium">Исполнитель</th>
                <th className="px-3 py-2 font-medium">Длина</th>
                <th className="px-3 py-2 font-medium">Score</th>
              </tr>
            </thead>
            <tbody>
              {current.tracks.map((track, index) => (
                <tr key={track.id} className="border-b border-slate-800/60 last:border-0">
                  <td className="px-3 py-2 text-slate-500">{index + 1}</td>
                  <td className="px-3 py-2">{track.title}</td>
                  <td className="px-3 py-2 text-slate-400">{track.artist}</td>
                  <td className="px-3 py-2 tabular-nums text-slate-400">
                    {formatDuration(track.duration_ms)}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-slate-300">
                    {formatScore(track.similarity_score)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
