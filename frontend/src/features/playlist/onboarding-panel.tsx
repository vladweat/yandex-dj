"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ONBOARDING_SITUATIONS } from "@/features/playlist/playlist-form-utils";

const STORAGE_KEY = "prompt_dj_onboarding_dismissed";

type OnboardingPanelProps = {
  onPickSituation: (prompt: string) => void;
};

export function OnboardingPanel({ onPickSituation }: OnboardingPanelProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      if (localStorage.getItem(STORAGE_KEY) !== "1") {
        setVisible(true);
      }
    } catch {
      setVisible(true);
    }
  }, []);

  function dismiss() {
    try {
      localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      // ignore quota / private mode
    }
    setVisible(false);
  }

  function pick(prompt: string) {
    onPickSituation(prompt);
    dismiss();
  }

  if (!visible) return null;

  return (
    <Card className="mb-6 border-slate-700 bg-slate-900/80">
      <CardHeader className="relative pr-12">
        <CardTitle>Как это работает</CardTitle>
        <CardDescription>
          Опишите ситуацию своими словами — Prompt DJ соберёт плейлист и сразу положит его в ваш
          аккаунт Яндекс Музыки. Обычно это занимает{" "}
          <span className="text-slate-200">7–20 секунд</span>.
        </CardDescription>
        <button
          type="button"
          onClick={dismiss}
          aria-label="Закрыть онбординг"
          className="absolute right-4 top-0 rounded-md p-1.5 text-slate-400 transition hover:bg-slate-800 hover:text-slate-100 sm:right-6"
        >
          <X className="size-4" />
        </button>
      </CardHeader>
      <CardContent className="space-y-4">
        <ul className="list-disc space-y-1 pl-5 text-sm text-slate-400">
          <li>Интерпретирует настроение и жанр, а не просто ищет ключевые слова</li>
          <li>Можно учесть лайки и недавнее («Учитывать мою библиотеку»)</li>
          <li>«Ещё вариант» — новый плейлист без повторного LLM</li>
        </ul>

        <div className="space-y-2">
          <p className="text-sm font-medium text-slate-200">Попробуйте ситуацию</p>
          <div className="grid gap-2 sm:grid-cols-3">
            {ONBOARDING_SITUATIONS.map((item) => (
              <Button
                key={item.prompt}
                type="button"
                variant="secondary"
                className="h-auto whitespace-normal px-3 py-2 text-left text-sm"
                onClick={() => pick(item.prompt)}
              >
                <span className="flex flex-col gap-0.5">
                  <span className="font-medium text-slate-100">{item.title}</span>
                  <span className="text-xs font-normal text-slate-400">{item.prompt}</span>
                </span>
              </Button>
            ))}
          </div>
        </div>

        <Button type="button" variant="ghost" size="sm" onClick={dismiss}>
          Понятно, закрыть
        </Button>
      </CardContent>
    </Card>
  );
}
