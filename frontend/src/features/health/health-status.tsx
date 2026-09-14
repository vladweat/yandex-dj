"use client";

import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FadeIn } from "@/components/ui/fade-in";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchHealth } from "@/lib/api";
import type { HealthResponse } from "@/types/health";

export function HealthStatus() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <Card>
        <CardContent className="space-y-2 pt-6">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-48" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return <Alert variant="destructive">Не удалось подключиться к API: {error}</Alert>;
  }

  if (!health) return null;

  const ok = health.status === "ok";

  return (
    <FadeIn>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-medium text-slate-400">API status</CardTitle>
          <Badge variant={ok ? "success" : "destructive"}>{health.status}</Badge>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-slate-400">version: {health.version}</p>
        </CardContent>
      </Card>
    </FadeIn>
  );
}
