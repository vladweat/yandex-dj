"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut } from "lucide-react";

import { useAuth } from "@/features/auth/auth-provider";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const PUBLIC_NAV = [
  {
    href: "/gallery",
    label: "Галерея",
    match: (path: string) => path.startsWith("/gallery"),
  },
];

const AUTH_NAV = [
  { href: "/", label: "Генерация", match: (path: string) => path === "/" },
  {
    href: "/lab",
    label: "Lab",
    match: (path: string) => path.startsWith("/lab") || path.startsWith("/debug"),
  },
];

export function AppHeader() {
  const { isAuthenticated, user, logout } = useAuth();
  const pathname = usePathname();
  const nav = isAuthenticated ? [...AUTH_NAV, ...PUBLIC_NAV] : PUBLIC_NAV;
  const isHome = pathname === "/";

  return (
    <header className="shrink-0 border-b border-white/[0.06] bg-black/20 pt-[env(safe-area-inset-top)] backdrop-blur-xl">
      <div className="mx-auto flex min-h-12 max-w-6xl items-center justify-between gap-2 px-4 py-2 sm:h-14 sm:px-6 sm:py-0">
        <div className="flex min-w-0 items-center gap-4 sm:gap-8">
          <Link href="/" className="group block shrink-0">
            <h1
              className={cn(
                "font-display text-[15px] font-semibold tracking-tight transition-colors sm:text-base",
                isHome ? "text-foreground" : "text-accent",
              )}
            >
              Prompt <span className="text-accent">DJ</span>
            </h1>
          </Link>
          <nav className="flex items-center gap-0.5">
            {nav.map((item) => {
              const active = item.match(pathname);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "rounded-lg px-2.5 py-1.5 text-[13px] font-medium tracking-wide transition-colors",
                    active
                      ? "bg-white/[0.06] text-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex min-w-0 shrink-0 items-center gap-2 text-sm">
          {isAuthenticated && user ? (
            <>
              <span className="hidden max-w-[160px] truncate text-[13px] text-muted-foreground lg:inline">
                {user.login}
              </span>
              <Button type="button" variant="ghost" size="sm" onClick={logout} aria-label="Выйти">
                <LogOut className="sm:hidden" />
                <span className="hidden sm:inline">Выйти</span>
              </Button>
            </>
          ) : pathname !== "/login" ? (
            <Button asChild variant="outline" size="sm">
              <Link href="/login">Войти</Link>
            </Button>
          ) : null}
        </div>
      </div>
    </header>
  );
}
