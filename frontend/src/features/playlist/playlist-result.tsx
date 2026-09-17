"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Copy, ExternalLink, Link2, Loader2, RefreshCw, ThumbsDown, ThumbsUp } from "lucide-react";
import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FadeIn } from "@/components/ui/fade-in";
import { clearSessionId, generatePlaylist, setPlaylistFeedback } from "@/lib/api";
import {
  classifyGenerateApiError,
  generationOptionsFromResult,
  promptDeepLink,
  pushGenerateWarnings,
} from "@/features/playlist/playlist-form-utils";
import { usePlaylistStore } from "@/features/playlist/stores/playlist-store";
import { useToastStore } from "@/stores/toast-store";
import type { FeedbackValue } from "@/types/playlist";
import { cn } from "@/lib/utils";

function formatDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${min}:${sec.toString().padStart(2, "0")}`;
}

function formatScore(score: number): string {
  return score.toFixed(3);
}

export type PlaylistResultVariant = "simple" | "full";

type PlaylistResultProps = {
  variant?: PlaylistResultVariant;
};

export function PlaylistResult({ variant = "simple" }: PlaylistResultProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const result = usePlaylistStore((state) => state.result);
  const setResult = usePlaylistStore((state) => state.setResult);
  const pushToast = useToastStore((state) => state.push);
  const [regenLoading, setRegenLoading] = useState(false);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [copyDone, setCopyDone] = useState(false);
  const [shareDone, setShareDone] = useState(false);
  const [tracksOpen, setTracksOpen] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // Reset collapsed track list when switching generations
  const resultId = usePlaylistStore((state) => state.result?.id);
  useEffect(() => {
    setTracksOpen(false);
  }, [resultId]);

  if (!result) return null;

  const current = result;
  const stats = current.pool_stats;
  const profile = current.profile;
  const currentFeedback = current.feedback ?? null;
  const isFull = variant === "full";

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

  async function handleSharePrompt() {
    const url = promptDeepLink(current.prompt, window.location.origin);
    try {
      await navigator.clipboard.writeText(url);
      setShareDone(true);
      pushToast("Ссылка на промпт скопирована", "info");
      window.setTimeout(() => setShareDone(false), 2000);
    } catch {
      pushToast("Не удалось скопировать", "error");
    }
  }

  async function handleFeedback(value: FeedbackValue) {
    const nextValue = currentFeedback === value ? null : value;
    const previous = currentFeedback;
    setResult({ ...current, feedback: nextValue });
    setFeedbackLoading(true);
    try {
      const response = await setPlaylistFeedback(current.id, { value: nextValue });
      setResult({ ...current, feedback: response.feedback });
      void queryClient.invalidateQueries({ queryKey: ["playlists", "history"] });
    } catch (err) {
      setResult({ ...current, feedback: previous });
      const action = classifyGenerateApiError(err);
      if (action.kind === "unauthorized") {
        clearSessionId();
        pushToast("Сессия истекла — войдите снова", "error");
        router.replace("/login");
      } else {
        pushToast("Не удалось сохранить оценку", "error");
      }
    } finally {
      setFeedbackLoading(false);
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
          use_library: opts.use_library,
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
      } else if (action.kind === "timeout" || action.kind === "quota" || action.kind === "message") {
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
    <FadeIn>
      <Card
        className={cn(
          "mt-5 gap-3 border-white/10 py-4 sm:mt-6 sm:py-5",
          !isFull &&
            "bg-gradient-to-b from-white/[0.05] to-white/[0.015] shadow-[0_20px_50px_-30px_rgba(0,0,0,0.8)]",
        )}
      >
        <CardHeader className={!isFull ? "gap-1" : undefined}>
          <CardTitle className={cn(!isFull && "font-display text-lg tracking-tight sm:text-xl")}>
            {current.title}
          </CardTitle>
          <CardDescription
            className={cn("whitespace-pre-wrap", !isFull && "line-clamp-2 text-sm")}
          >
            {current.description}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Button asChild size={isFull ? "default" : "lg"} className={cn(!isFull && "min-h-11")}>
              <a href={current.playlist_url} target="_blank" rel="noopener noreferrer">
                Открыть в Яндекс Музыке
                <ExternalLink />
              </a>
            </Button>
            <Button
              type="button"
              variant={currentFeedback === "like" ? "default" : "outline"}
              size="icon"
              aria-label="Нравится"
              aria-pressed={currentFeedback === "like"}
              disabled={feedbackLoading || regenLoading}
              onClick={() => void handleFeedback("like")}
              className={cn(!isFull && "size-11")}
            >
              <ThumbsUp />
            </Button>
            <Button
              type="button"
              variant={currentFeedback === "dislike" ? "default" : "outline"}
              size="icon"
              aria-label="Не нравится"
              aria-pressed={currentFeedback === "dislike"}
              disabled={feedbackLoading || regenLoading}
              onClick={() => void handleFeedback("dislike")}
              className={cn(!isFull && "size-11")}
            >
              <ThumbsDown />
            </Button>
            {isFull ? (
              <>
                <Button type="button" variant="secondary" onClick={handleCopy}>
                  <Copy />
                  {copyDone ? "Скопировано" : "Копировать ссылку и промпт"}
                </Button>
                <Button type="button" variant="outline" onClick={handleSharePrompt}>
                  <Link2 />
                  {shareDone ? "Скопировано" : "Поделиться промптом"}
                </Button>
              </>
            ) : null}
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
              <Button type="button" variant="ghost" onClick={() => abortRef.current?.abort()}>
                Отменить
              </Button>
            ) : null}
            {isFull ? (
              <>
                <Badge variant="secondary">{current.tracks.length} треков</Badge>
                {current.options?.use_library ? (
                  <Badge variant="secondary">с библиотекой</Badge>
                ) : null}
                {stats ? (
                  <>
                    <Badge variant="outline">raw {stats.raw}</Badge>
                    <Badge variant="outline">clean {stats.clean}</Badge>
                    <Badge variant="outline">selected {stats.selected}</Badge>
                  </>
                ) : null}
              </>
            ) : (
              <span className="text-sm text-slate-500">{current.tracks.length} треков</span>
            )}
          </div>

          {!isFull ? (
            <div className="flex flex-wrap gap-3 text-sm">
              <button
                type="button"
                onClick={() => void handleSharePrompt()}
                className="text-slate-400 underline-offset-2 hover:text-slate-200 hover:underline"
              >
                {shareDone ? "Ссылка скопирована" : "Поделиться промптом"}
              </button>
              <button
                type="button"
                onClick={() => void handleCopy()}
                className="text-slate-400 underline-offset-2 hover:text-slate-200 hover:underline"
              >
                {copyDone ? "Скопировано" : "Копировать ссылку"}
              </button>
              {current.tracks.length > 0 ? (
                <button
                  type="button"
                  onClick={() => setTracksOpen((open) => !open)}
                  className="text-slate-400 underline-offset-2 hover:text-slate-200 hover:underline"
                  aria-expanded={tracksOpen}
                >
                  {tracksOpen ? "Скрыть треки" : `Треки (${current.tracks.length})`}
                </button>
              ) : null}
            </div>
          ) : null}

          {isFull ? (
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
          ) : null}

          {isFull ? (
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
          ) : tracksOpen && current.tracks.length > 0 ? (
            <ol className="max-h-[40vh] divide-y divide-slate-800/80 overflow-y-auto rounded-xl border border-slate-800/80">
              {current.tracks.map((track, index) => (
                <li
                  key={track.id}
                  className="flex items-baseline gap-3 px-3 py-2 text-sm sm:px-4"
                >
                  <span className="w-5 shrink-0 tabular-nums text-slate-600">{index + 1}</span>
                  <span className="min-w-0 flex-1 truncate text-slate-200">{track.title}</span>
                  <span className="max-w-[40%] truncate text-slate-500">{track.artist}</span>
                </li>
              ))}
            </ol>
          ) : null}
        </CardContent>
      </Card>
    </FadeIn>
  );
}
