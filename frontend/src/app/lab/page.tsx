import type { Metadata } from "next";

import { AuthGate } from "@/features/auth/auth-gate";
import { LabPage } from "@/features/playlist/lab-page";

export const metadata: Metadata = {
  title: "Lab — Prompt DJ",
};

export default function LabRoute() {
  return (
    <AuthGate>
      <LabPage />
    </AuthGate>
  );
}
