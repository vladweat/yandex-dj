import type { Metadata } from "next";

import { AuthGate } from "@/features/auth/auth-gate";
import { DebugPage } from "@/features/debug/debug-page";

export const metadata: Metadata = {
  title: "Отладка — Prompt DJ",
};

export default function DebugRoute() {
  return (
    <AuthGate>
      <DebugPage />
    </AuthGate>
  );
}
