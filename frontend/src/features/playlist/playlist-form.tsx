"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { clearSessionId, generatePlaylist } from "@/lib/api";
import { usePlaylistStore } from "@/features/playlist/stores/playlist-store";
import { useToastStore } from "@/stores/toast-store";
import type { DiversityMode } from "@/types/playlist";
import { cn } from "@/lib/utils";
import {
  classifyGenerateApiError,
  parseExcludeArtists,
  pushGenerateWarnings,
  SAMPLE_PROMPTS,
  validatePlaylistFormInput,
} from "@/features/playlist/playlist-form-utils";

const selectClassName = cn(
  "flex h-11 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-base text-slate-100 outline-none transition-colors focus:border-blue-500 disabled:opacity-50 sm:h-9 sm:text-sm",
);

export function PlaylistForm() {
  const router = useRouter();
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
  const [sourceId, setSourceId] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [apiUnavailable, setApiUnavailable] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

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
    setSourceId(draft.sourceId);
    setDraft(null);
  }, [draft, setDraft]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  async function runGenerate(overrides?: { sourceId?: string | null }) {
    setValidationError(null);
    setApiUnavailable(false);

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
          source_id: nextSourceId,
        },
        { signal: controller.signal },
      );
      setResult(response);
      setSourceId(null);
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
      } else if (action.kind === "validation") {
        setValidationError(action.message);
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
    <form onSubmit={handleSubmit} className="space-y-4">
      {apiUnavailable ? (
        <Alert variant="destructive">
          <AlertDescription>
            API недоступен. Проверьте, что backend запущен, и попробуйте снова.
          </AlertDescription>
        </Alert>
      ) : null}

      <div>
        <Label htmlFor="prompt">Опишите плейлист</Label>
        <Textarea
          id="prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Саундтрек для ночной поездки по пустому шоссе в стиле нео-нуар и синтвейв"
          rows={4}
          disabled={submitting}
        />
        <div className="mt-2 flex flex-wrap gap-2">
          {SAMPLE_PROMPTS.map((sample) => (
            <button
              key={sample}
              type="button"
              disabled={submitting}
              onClick={() => setPrompt(sample)}
              className="rounded-md border border-slate-700 bg-slate-950/40 px-2.5 py-1 text-left text-xs text-slate-300 transition hover:border-accent/50 hover:text-foreground disabled:opacity-50"
            >
              {sample}
            </button>
          ))}
        </div>
        {validationError ? <p className="mt-1 text-sm text-red-400">{validationError}</p> : null}
      </div>

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

      {sourceId ? (
        <p className="text-xs text-slate-400">
          Режим «ещё вариант»: профиль возьмём из прошлой генерации (без LLM).
        </p>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={submitting} className="w-full sm:w-auto">
          {submitting ? (
            <>
              <Loader2 className="animate-spin" />
              Генерируем… (обычно 7–20 сек)
            </>
          ) : (
            "Сгенерировать плейлист"
          )}
        </Button>
        {submitting ? (
          <Button type="button" variant="outline" onClick={handleCancel} className="w-full sm:w-auto">
            Отменить
          </Button>
        ) : null}
      </div>
    </form>
  );
}
