import type { Metadata, Viewport } from "next";

import { AppHeader } from "@/components/app-header";
import { AuthProvider } from "@/features/auth/auth-provider";
import { QueryProvider } from "@/components/query-provider";
import { ToastHost } from "@/components/toast-host";

import "./globals.css";

export const metadata: Metadata = {
  title: "Prompt DJ",
  description: "Генерация плейлистов Яндекс Музыки из текстового промпта",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#080a0f",
  interactiveWidget: "resizes-content",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&family=Unbounded:wght@500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="flex h-dvh flex-col overflow-hidden antialiased">
        <QueryProvider>
          <AuthProvider>
            <AppHeader />
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{children}</div>
            <ToastHost />
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
