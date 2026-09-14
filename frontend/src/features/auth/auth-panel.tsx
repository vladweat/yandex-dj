"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ExternalLink, Loader2 } from "lucide-react";

import { useAuth } from "@/features/auth/auth-provider";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { ApiRequestError, pollDeviceFlow, startDeviceFlow } from "@/lib/api";
import type { DeviceFlowStartResponse } from "@/types/auth";

type FlowPhase = "idle" | "starting" | "waiting" | "polling" | "error";

export function AuthPanel() {
  const { completeLogin, error, clearError } = useAuth();
  const [phase, setPhase] = useState<FlowPhase>("idle");
  const [flow, setFlow] = useState<DeviceFlowStartResponse | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelledRef = useRef(false);

  const clearPollTimer = useCallback(() => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const schedulePoll = useCallback(
    (deviceCode: string, intervalSec: number) => {
      clearPollTimer();
      pollTimerRef.current = setTimeout(async () => {
        if (cancelledRef.current) return;
        setPhase("polling");
        try {
          const result = await pollDeviceFlow({ device_code: deviceCode });
          if (cancelledRef.current) return;
          if (result.status === "authenticated" && result.session_id) {
            clearPollTimer();
            await completeLogin(result.session_id);
            return;
          }
          schedulePoll(deviceCode, intervalSec);
          setPhase("waiting");
        } catch (err) {
          clearPollTimer();
          const message =
            err instanceof ApiRequestError ? err.message : "Ошибка при проверке авторизации";
          setLocalError(message);
          setPhase("error");
        }
      }, intervalSec * 1000);
    },
    [clearPollTimer, completeLogin],
  );

  const startFlow = useCallback(async () => {
    clearError();
    setLocalError(null);
    cancelledRef.current = false;
    clearPollTimer();
    setPhase("starting");
    try {
      const started = await startDeviceFlow();
      if (cancelledRef.current) return;
      setFlow(started);
      setPhase("waiting");
      schedulePoll(started.device_code, started.interval);
    } catch (err) {
      const message =
        err instanceof ApiRequestError ? err.message : "Не удалось начать авторизацию";
      setLocalError(message);
      setPhase("error");
    }
  }, [clearError, clearPollTimer, schedulePoll]);

  useEffect(() => {
    cancelledRef.current = false;
    void startFlow();
    return () => {
      cancelledRef.current = true;
      clearPollTimer();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once on mount
  }, []);

  const displayError = localError ?? error;

  return (
    <Panel
      title="Вход через Яндекс"
      subtitle="Подтвердите вход на ya.ru/device — мы подождём автоматически"
    >
      {phase === "starting" ? (
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <Loader2 className="size-4 animate-spin" />
          Получаем код…
        </div>
      ) : null}

      {flow && phase !== "starting" ? (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-center">
            <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">Код устройства</p>
            <p className="text-2xl font-bold tracking-widest text-[#ffcc00]">{flow.user_code}</p>
          </div>

          <Button asChild variant="secondary" className="w-full">
            <a href={flow.verification_url} target="_blank" rel="noopener noreferrer">
              Открыть ya.ru/device
              <ExternalLink />
            </a>
          </Button>

          {phase === "polling" || phase === "waiting" ? (
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <Loader2 className="size-4 animate-spin" />
              Ожидаем подтверждение…
            </div>
          ) : null}

          <p className="text-xs text-slate-500">
            Код действует {Math.floor(flow.expires_in / 60)} мин. После входа вы будете перенаправлены
            автоматически.
          </p>
        </div>
      ) : null}

      {displayError ? <Alert variant="destructive">{displayError}</Alert> : null}

      {phase === "error" ? (
        <Button type="button" onClick={() => void startFlow()} className="w-full">
          Попробовать снова
        </Button>
      ) : null}
    </Panel>
  );
}
