"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiRequestError, clearSessionId, generatePlaylist } from "@/lib/api";
import { usePlaylistStore } from "@/features/playlist/stores/playlist-store";
import { useToastStore } from "@/stores/toast-store";

const SAMPLE_PROMPTS = [
  "под настроение пока варю макароны",
  "спокойная музыка для кодинга поздней ночью",
  "саундтрек для ночной поездки в стиле синтвейв",
] as const;

export function PlaylistForm() {
  const router = useRouter();
  const setResult = usePlaylistStore((state) => state.setResult);
  const pushToast = useToastStore((state) => state.push);
  const [prompt, setPrompt] = useState("");
  const [trackCount, setTrackCount] = useState(25);
  const [instrumentalOnly, setInstrumentalOnly] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setValidationError(null);

    const trimmed = prompt.trim();
    if (!trimmed) {
      setValidationError("Введите описание плейлиста");
      return;
    }
    if (trimmed.length > 2000) {
      setValidationError("Промпт не длиннее 2000 символов");
      return;
    }
    if (!Number.isFinite(trackCount) || trackCount < 1 || trackCount > 50) {
      setValidationError("Количество треков: от 1 до 50");
      return;
    }

    setSubmitting(true);
    setResult(null);
    try {
      const response = await generatePlaylist({
        prompt: trimmed,
        track_count: trackCount,
        instrumental_only: instrumentalOnly,
      });
      setResult(response);
    } catch (err) {
      if (err instanceof ApiRequestError) {
        if (err.status === 401) {
          clearSessionId();
          pushToast("Сессия истекла — войдите снова", "error");
          router.replace("/login");
          return;
        }
        if (err.status === 422) {
          setValidationError(err.message);
          return;
        }
        if (err.status === 502 || err.status === 503) {
          pushToast("Сервис временно недоступен", "error");
          return;
        }
        pushToast(err.message, "error");
        return;
      }
      pushToast("Не удалось сгенерировать плейлист", "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
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

        <div className="flex items-end gap-2 pb-2">
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
      </div>

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
    </form>
  );
}
