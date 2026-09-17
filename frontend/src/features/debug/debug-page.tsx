"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";

import { useAuth } from "@/features/auth/auth-provider";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FadeIn } from "@/components/ui/fade-in";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiRequestError, fetchYandexAccount } from "@/lib/api";
import type { YandexStatusResponse } from "@/types/yandex";

function JsonBlock({ data }: { data: unknown }) {
  return (
    <pre className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-950/80 p-3 text-xs text-slate-300">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 sm:flex-row sm:items-center sm:justify-between">
      <span className="text-sm text-slate-500">{label}</span>
      <span className="font-mono text-sm text-slate-200 break-all">{value}</span>
    </div>
  );
}

export function DebugPage() {
  const { refreshUser } = useAuth();
  const [yandex, setYandex] = useState<YandexStatusResponse | null>(null);
  const [yandexError, setYandexError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setYandexError(null);
    try {
      setYandex(await fetchYandexAccount());
    } catch (err) {
      setYandex(null);
      setYandexError(
        err instanceof ApiRequestError ? `${err.message} (${err.status})` : "Ошибка запроса к Яндексу",
      );
    }
  }, []);

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, [load]);

  async function handleRefresh() {
    setRefreshing(true);
    await refreshUser();
    await load();
    setRefreshing(false);
  }

  const account = yandex?.account;

  return (
    <main className="flex-1 overflow-y-auto px-4 py-8 sm:px-6 sm:py-10">
      <div className="mx-auto flex max-w-2xl flex-col gap-6">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="font-display text-xl font-semibold tracking-tight">Яндекс account</h2>
            <p className="text-sm text-slate-400">
              account/status. Полная генерация — в{" "}
              <Link href="/lab" className="text-slate-300 underline-offset-2 hover:underline">
                Lab
              </Link>
              .
            </p>
          </div>
          <Button type="button" variant="secondary" size="sm" disabled={refreshing} onClick={() => void handleRefresh()}>
            {refreshing ? <Loader2 className="animate-spin" /> : <RefreshCw />}
            Обновить
          </Button>
        </div>

        <FadeIn>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Яндекс Музыка</CardTitle>
                <CardDescription>GET /api/v1/yandex/account → ClientAsync.account_status()</CardDescription>
              </div>
              {account?.service_available ? (
                <Badge variant="success">доступен</Badge>
              ) : account ? (
                <Badge variant="destructive">недоступен</Badge>
              ) : null}
            </CardHeader>
            <CardContent className="space-y-4">
              {loading ? (
                <div className="space-y-2">
                  <Skeleton className="h-4 w-48" />
                  <Skeleton className="h-4 w-64" />
                  <Skeleton className="h-32 w-full" />
                </div>
              ) : yandexError ? (
                <Alert variant="destructive">{yandexError}</Alert>
              ) : yandex && account ? (
                <>
                  <div className="space-y-3">
                    <InfoRow label="uid" value={String(account.uid ?? "—")} />
                    <InfoRow label="login" value={account.login ?? "—"} />
                    <InfoRow label="display_name" value={account.display_name ?? "—"} />
                    <InfoRow label="full_name" value={account.full_name ?? "—"} />
                    <InfoRow label="email" value={yandex.default_email ?? "—"} />
                    <InfoRow label="region" value={String(account.region ?? "—")} />
                    <InfoRow label="registered_at" value={account.registered_at ?? "—"} />
                  </div>

                  {yandex.plus ? (
                    <div>
                      <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Plus</p>
                      <JsonBlock data={yandex.plus} />
                    </div>
                  ) : null}

                  {yandex.subscription ? (
                    <div>
                      <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Subscription</p>
                      <JsonBlock data={yandex.subscription} />
                    </div>
                  ) : null}

                  <div>
                    <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Полный ответ</p>
                    <JsonBlock data={yandex.status} />
                  </div>
                </>
              ) : (
                <Alert>Нет данных от Яндекса</Alert>
              )}
            </CardContent>
          </Card>
        </FadeIn>
      </div>
    </main>
  );
}
