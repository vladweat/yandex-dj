"use client";

import { useEffect, useRef } from "react";

import { useAuth } from "@/features/auth/auth-provider";
import { AppRoutesProvider } from "@/features/telegram/app-routes";
import { linkTelegramAccount } from "@/lib/api";
import { setClientChannel } from "@/lib/client-channel";

type TgShellProps = {
  children: React.ReactNode;
};

async function loadTelegramWebApp() {
  const { default: WebApp } = await import("@twa-dev/sdk");
  return WebApp;
}

export function TgShell({ children }: TgShellProps) {
  const { isAuthenticated } = useAuth();
  const linkedRef = useRef(false);

  useEffect(() => {
    setClientChannel("telegram");
    let cancelled = false;
    void loadTelegramWebApp().then((WebApp) => {
      if (cancelled) return;
      WebApp.ready();
      WebApp.expand();
    });
    return () => {
      cancelled = true;
      setClientChannel("web");
    };
  }, []);

  useEffect(() => {
    if (!isAuthenticated || linkedRef.current) return;
    void loadTelegramWebApp().then((WebApp) => {
      const initData = WebApp.initData;
      if (!initData || linkedRef.current) return;
      linkedRef.current = true;
      void linkTelegramAccount(initData).catch(() => {
        linkedRef.current = false;
      });
    });
  }, [isAuthenticated]);

  return (
    <AppRoutesProvider value={{ loginPath: "/tg/login", isTelegram: true }}>
      {children}
    </AppRoutesProvider>
  );
}
