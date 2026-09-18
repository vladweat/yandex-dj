"use client";

import WebApp from "@twa-dev/sdk";
import { useEffect, useRef } from "react";

import { useAuth } from "@/features/auth/auth-provider";
import { AppRoutesProvider } from "@/features/telegram/app-routes";
import { linkTelegramAccount } from "@/lib/api";
import { setClientChannel } from "@/lib/client-channel";

type TgShellProps = {
  children: React.ReactNode;
};

export function TgShell({ children }: TgShellProps) {
  const { isAuthenticated } = useAuth();
  const linkedRef = useRef(false);

  useEffect(() => {
    setClientChannel("telegram");
    WebApp.ready();
    WebApp.expand();
    return () => setClientChannel("web");
  }, []);

  useEffect(() => {
    if (!isAuthenticated || linkedRef.current) return;
    const initData = WebApp.initData;
    if (!initData) return;
    linkedRef.current = true;
    void linkTelegramAccount(initData).catch(() => {
      linkedRef.current = false;
    });
  }, [isAuthenticated]);

  return (
    <AppRoutesProvider value={{ loginPath: "/tg/login", isTelegram: true }}>
      {children}
    </AppRoutesProvider>
  );
}
