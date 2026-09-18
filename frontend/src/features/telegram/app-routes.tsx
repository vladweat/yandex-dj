"use client";

import { createContext, useContext, type ReactNode } from "react";

export type AppRoutes = {
  loginPath: string;
  isTelegram: boolean;
};

const defaultRoutes: AppRoutes = {
  loginPath: "/login",
  isTelegram: false,
};

const AppRoutesContext = createContext<AppRoutes>(defaultRoutes);

export function AppRoutesProvider({
  value,
  children,
}: {
  value: AppRoutes;
  children: ReactNode;
}) {
  return <AppRoutesContext.Provider value={value}>{children}</AppRoutesContext.Provider>;
}

export function useAppRoutes(): AppRoutes {
  return useContext(AppRoutesContext);
}
