"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, type ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/features/auth/auth-provider";

function GateStatus({ label }: { label: string }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 py-10">
      <Skeleton className="h-4 w-40" />
      <p className="text-sm text-slate-400">{label}</p>
    </div>
  );
}

function AuthGateInner({ children }: { children: ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (loading || isAuthenticated) return;
    if (!pathname || pathname === "/login") return;
    const query = searchParams.toString();
    const target = query ? `${pathname}?${query}` : pathname;
    router.replace(`/login?next=${encodeURIComponent(target)}`);
  }, [isAuthenticated, loading, pathname, router, searchParams]);

  if (loading) {
    return <GateStatus label="Загрузка…" />;
  }
  if (!isAuthenticated) {
    return <GateStatus label="Перенаправление на вход…" />;
  }
  return <div className="flex min-h-0 flex-1 flex-col">{children}</div>;
}

export function AuthGate({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<GateStatus label="Загрузка…" />}>
      <AuthGateInner>{children}</AuthGateInner>
    </Suspense>
  );
}
