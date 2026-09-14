import type { Metadata } from "next";

import { HealthStatus } from "@/features/health/health-status";

export const metadata: Metadata = {
  title: "Health — Prompt DJ",
};

export default function HealthPage() {
  return (
    <main className="flex-1 overflow-y-auto px-4 py-8 sm:px-6">
      <div className="mx-auto max-w-md">
        <HealthStatus />
      </div>
    </main>
  );
}
