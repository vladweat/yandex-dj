import type { Metadata } from "next";

import { TgShell } from "@/features/telegram/tg-shell";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Prompt DJ — Telegram",
};

export default function TelegramLayout({ children }: { children: React.ReactNode }) {
  return <TgShell>{children}</TgShell>;
}
