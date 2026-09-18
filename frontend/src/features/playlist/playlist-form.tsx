"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAppRoutes } from "@/features/telegram/app-routes";
import { clearSessionId, fetchPlaylistQuota, generatePlaylist } from "@/lib/api";
import { usePlaylistStore } from "@/features/playlist/stores/playlist-store";
import { useToastStore } from "@/stores/toast-store";
import type { DiversityMode } from "@/types/playlist";
import { cn } from "@/lib/utils";
import {
  classifyGenerateApiError,
  GENERATION_LATENCY_HINT,
  ONBOARDING_SITUATIONS,
  parseExcludeArtists,
  pushGenerateWarnings,
  REGEN_LATENCY_HINT,
  SAMPLE_PROMPTS,
  validatePlaylistFormInput,
} from "@/features/playlist/playlist-form-utils";

const selectClassName = cn(
  "flex h-11 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-base text-slate-100 outline-none transition-colors focus:border-accent/70 disabled:opacity-50 sm:h-9 sm:text-sm",
);

const LOADING_HINTS = [
  "Слушаем промпт…",
  "Подбираем треки…",
  "Собираем плейлист в Яндексе…",
] as const;

export type PlaylistFormVariant = "simple" | "full";

type PlaylistFormProps = {
  variant?: PlaylistFormVariant;
  /** Tighter spacing when result already fills the viewport */
  compact?: boolean;
};

export function PlaylistForm({ variant = "simple", compact = false }: PlaylistFormProps) {
  const router = useRouter();
  const { loginPath } = useAppRoutes();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const setResult = usePlaylistStore((state) => state.setResult);
  const draft = usePlaylistStore((state) => state.draft);
  const setDraft = usePlaylistStore((state) => state.setDraft);
  const pushToast = useToastStore((state) => state.push);

  const [prompt, setPrompt] = useState("");
  const [trackCount, setTrackCount] = useState(25);
  const [instrumentalOnly, setInstrumentalOnly] = useState(false);
  const [excludeArtists, setExcludeArtists] = useState("");
  const [diversity, setDiversity] = useState<DiversityMode>("normal");
  const [useLibrary, setUseLibrary] = useState(false);
  const [sourceId, setSourceId] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [apiUnavailable, setApiUnavailable] = useState(false);
  const [quotaBlocked, setQuotaBlocked] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [loadingHintIndex, setLoadingHintIndex] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  const isFull = variant === "full";

  const quotaQuery = useQuery({
    queryKey: ["playlists", "quota"],
    queryFn: fetchPlaylistQuota,
    staleTime: 30_000,
  });
  const quota = quotaQuery.data;
  const quotaExhausted =
    Boolean(quota) && !quota!.unlimited && quota!.remaining <= 0 && !sourceId;

  useEffect(() => {
    const fromQuery = searchParams.get("prompt");
    if (fromQuery?.trim()) {
      setPrompt(fromQuery);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!draft) return;
    setPrompt(draft.prompt);
    setTrackCount(draft.trackCount);
    setInstrumentalOnly(draft.instrumentalOnly);
    setExcludeArtists(draft.excludeArtists);
    setDiversity(draft.diversity);
    setUseLibrary(draft.useLibrary);
    setSourceId(draft.sourceId);
    setDraft(null);
  }, [draft, setDraft]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    if (!submitting) {
      setLoadingHintIndex(0);
      return;
    }
    const timer = window.setInterval(() => {
      setLoadingHintIndex((i) => (i + 1) % LOADING_HINTS.length);
    }, 3500);
    return () => window.clearInterval(timer);
  }, [submitting]);

  async function runGenerate(overrides?: { sourceId?: string | null }) {
    setValidationError(null);
    setApiUnavailable(false);
    setQuotaBlocked(false);

    const validation = validatePlaylistFormInput({ prompt, trackCount });
    if (validation) {
      setValidationError(validation);
      return;
    }

    const trimmed = prompt.trim();
    const nextSourceId = overrides?.sourceId !== undefined ? overrides.sourceId : sourceId;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setSubmitting(true);
    setResult(null);
    try {
      const response = await generatePlaylist(
        {
          prompt: trimmed,
          track_count: trackCount,
          instrumental_only: instrumentalOnly,
          exclude_artists: parseExcludeArtists(excludeArtists),
          diversity,
          use_library: useLibrary,
          source_id: nextSourceId,
        },
        { signal: controller.signal },
      );
      setResult(response);
      setSourceId(null);
      pushGenerateWarnings(response, pushToast);
      void queryClient.invalidateQueries({ queryKey: ["playlists", "history"] });
      void queryClient.invalidateQueries({ queryKey: ["playlists", "quota"] });
    } catch (err) {
      const action = classifyGenerateApiError(err);
      if (action.kind === "cancelled") {
        pushToast("Генерация отменена", "info");
      } else if (action.kind === "unauthorized") {
        clearSessionId();
        pushToast("Сессия истекла — войдите снова", "error");
        router.replace(loginPath);
      } else if (action.kind === "validation") {
        setValidationError(action.message);
      } else if (action.kind === "quota") {
        setQuotaBlocked(true);
        pushToast(action.message, "error");
        void queryClient.invalidateQueries({ queryKey: ["playlists", "quota"] });
      } else if (action.kind === "timeout") {
        pushToast(action.message, "error");
      } else if (action.kind === "unavailable") {
        setApiUnavailable(true);
        pushToast("API недоступен", "error");
      } else {
        pushToast(action.message, "error");
      }
    } finally {
      setSubmitting(false);
      abortRef.current = null;
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    await runGenerate({ sourceId: null });
  }

  function handleCancel() {
    abortRef.current?.abort();
  }

  return (
    <form onSubmit={handleSubmit} className={cn("space-y-4", compact && "space-y-3")}>
      {apiUnavailable ? (
        <Alert variant="destructive">
          <AlertDescription>
            Сервис временно недоступен. Попробуйте ещё раз через минуту.
          </AlertDescription>
        </Alert>
      ) : null}

      {quotaBlocked || quotaExhausted ? (
        <Alert variant="warning">
          <AlertDescription>
            Дневной лимит новых генераций исчерпан
            {quota && !quota.unlimited ? ` (${quota.limit}/сутки)` : ""}. Можно открыть прошлый
            плейлист из истории или нажать «Ещё вариант» — сброс в полночь UTC.
          </AlertDescription>
        </Alert>
      ) : null}

      <div>
        {isFull ? (
          <Label htmlFor="prompt">Опишите плейлист</Label>
        ) : (
          <Label htmlFor="prompt" className="sr-only">
            Опишите плейлист
          </Label>
        )}
        <Textarea
          id="prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Саундтрек для ночной поездки по пустому шоссе…"
          rows={isFull ? 4 : compact ? 3 : 5}
          disabled={submitting}
          className={cn(
            !isFull &&
              "rounded-[1.25rem] border-white/10 bg-white/[0.035] px-4 py-4 text-[15px] leading-relaxed tracking-[0.01em] shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] placeholder:text-muted-foreground/55 focus:border-accent/45 sm:text-[15px]",
            !isFull && (compact ? "min-h-[5.25rem]" : "min-h-[9rem]"),
          )}
        />
        <div className={cn("flex flex-wrap gap-2", compact ? "mt-2.5" : "mt-3.5")}>
          {isFull
            ? SAMPLE_PROMPTS.map((sample) => (
                <button
                  key={sample}
                  type="button"
                  disabled={submitting}
                  onClick={() => setPrompt(sample)}
                  className="rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1 text-left text-xs text-muted-foreground transition hover:border-accent/35 hover:text-foreground disabled:opacity-50"
                >
                  {sample}
                </button>
              ))
            : !compact
              ? ONBOARDING_SITUATIONS.map((item) => (
                  <button
                    key={item.prompt}
                    type="button"
                    disabled={submitting}
                    onClick={() => setPrompt(item.prompt)}
                    className="rounded-full border border-white/10 bg-white/[0.03] px-3.5 py-1.5 text-[13px] font-medium text-muted-foreground transition hover:border-accent/40 hover:bg-accent/10 hover:text-foreground disabled:opacity-50"
                  >
                    {item.title}
                  </button>
                ))
              : null}
        </div>
        {!isFull && !compact ? (
          <p className="mt-2.5 text-[12px] text-muted-foreground/80">
            Или выберите из{" "}
            <Link
              href="/gallery"
              className="font-medium text-foreground/80 underline-offset-2 transition hover:text-accent hover:underline"
            >
              галереи промптов
            </Link>
          </p>
        ) : isFull ? (
          <p className="mt-2 text-xs text-muted-foreground">
            <Link href="/gallery" className="underline-offset-2 hover:underline">
              Все промпты →
            </Link>
          </p>
        ) : null}
        {validationError ? <p className="mt-2 text-sm text-red-400">{validationError}</p> : null}
      </div>

      {isFull ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="track-count">Количество треков</Label>
              <Input
                id="track-count"
                type="number"
                min={1}
                max={50}
                value={trackCount}
                onChange={(e) => setTrackCount(Number(e.target.value))}
                disabled={submitting}
              />
            </div>

            <div>
              <Label htmlFor="diversity">Разнообразие</Label>
              <select
                id="diversity"
                className={selectClassName}
                value={diversity}
                onChange={(e) => setDiversity(e.target.value as DiversityMode)}
                disabled={submitting}
              >
                <option value="normal">Обычное</option>
                <option value="high">Больше разнообразия</option>
              </select>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Checkbox
              id="instrumental"
              checked={instrumentalOnly}
              onCheckedChange={(checked) => setInstrumentalOnly(checked === true)}
              disabled={submitting}
            />
            <Label htmlFor="instrumental" className="mb-0 cursor-pointer">
              Только инструментальная музыка
            </Label>
          </div>
        </>
      ) : null}

      <div className={cn("flex items-center gap-2", !isFull && "pt-1")}>
        <Checkbox
          id="use-library"
          checked={useLibrary}
          onCheckedChange={(checked) => setUseLibrary(checked === true)}
          disabled={submitting}
        />
        <Label
          htmlFor="use-library"
          className={cn(
            "mb-0 cursor-pointer",
            !isFull && "text-[13px] font-medium text-muted-foreground",
          )}
        >
          Учитывать мою библиотеку
        </Label>
      </div>
      {isFull ? (
        <p className="text-xs text-muted-foreground">
          Лайки и недавнее слегка подтянут пул под ваш вкус
        </p>
      ) : null}

      {isFull ? (
        <div>
          <Label htmlFor="exclude-artists">Исключить артистов</Label>
          <Textarea
            id="exclude-artists"
            value={excludeArtists}
            onChange={(e) => setExcludeArtists(e.target.value)}
            placeholder="Kavinsky, Perturbator"
            rows={2}
            disabled={submitting}
          />
          <p className="mt-1 text-xs text-slate-500">Через запятую, до 20 имён</p>
        </div>
      ) : null}

      {sourceId && isFull ? (
        <p className="text-xs text-slate-400">
          Режим «ещё вариант»: профиль возьмём из прошлой генерации (без LLM).
        </p>
      ) : null}

      {quota && !quota.unlimited ? (
        <p className={cn("text-xs", isFull ? "text-slate-500" : "text-[12px] text-muted-foreground/75")}>
          Сегодня осталось {quota.remaining} из {quota.limit} новых генераций
          {isFull ? " («Ещё вариант» не считается)" : ""}
        </p>
      ) : null}

      <div className={cn("flex flex-wrap gap-2", !isFull && "pt-1")}>
        <Button
          type="submit"
          disabled={submitting || quotaExhausted}
          size={isFull ? "default" : "lg"}
          className={cn("w-full sm:w-auto", !isFull && "min-h-12 px-7")}
        >
          {submitting ? (
            <>
              <Loader2 className="animate-spin" />
              {isFull ? "Генерируем… (обычно 7–20 сек)" : LOADING_HINTS[loadingHintIndex]}
            </>
          ) : (
            "Собрать плейлист"
          )}
        </Button>
        {submitting ? (
          <Button type="button" variant="outline" onClick={handleCancel} className="w-full sm:w-auto">
            Отменить
          </Button>
        ) : null}
      </div>

      {!isFull && submitting ? (
        <p className="text-[12px] text-muted-foreground/75">
          Обычно {GENERATION_LATENCY_HINT} — можно свернуть вкладку
        </p>
      ) : null}

      {!submitting ? (
        <p
          className={cn(
            "text-[12px] leading-relaxed text-muted-foreground/75",
            isFull ? "text-slate-500" : "",
          )}
        >
          Новая генерация — обычно {GENERATION_LATENCY_HINT}. {REGEN_LATENCY_HINT}.
        </p>
      ) : null}
    </form>
  );
}
