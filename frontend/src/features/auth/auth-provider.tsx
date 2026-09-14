"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  ApiRequestError,
  clearSessionId,
  fetchMe,
  setSessionId,
} from "@/lib/api";
import { resetClientSessionState } from "@/lib/reset-client-state";
import type { AuthMeResponse } from "@/types/auth";

interface AuthContextValue {
  user: AuthMeResponse | null;
  loading: boolean;
  error: string | null;
  isAuthenticated: boolean;
  completeLogin: (sessionId: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<AuthMeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const sessionIdRef = useRef<string | null>(null);

  const applyUser = useCallback(
    (next: AuthMeResponse | null) => {
      const nextSessionId = next?.session_id ?? null;
      if (sessionIdRef.current !== nextSessionId) {
        resetClientSessionState(queryClient);
        sessionIdRef.current = nextSessionId;
      }
      setUser(next);
    },
    [queryClient],
  );

  const refreshUser = useCallback(async () => {
    try {
      const me = await fetchMe();
      applyUser(me);
    } catch (err) {
      if (err instanceof ApiRequestError && err.status === 401) {
        clearSessionId();
        applyUser(null);
      }
    }
  }, [applyUser]);

  useEffect(() => {
    let cancelled = false;

    const boot = async () => {
      for (let attempt = 0; attempt < 8; attempt += 1) {
        if (cancelled) return;
        try {
          const me = await fetchMe();
          if (!cancelled) applyUser(me);
          return;
        } catch (err) {
          if (err instanceof ApiRequestError && err.status === 401) {
            clearSessionId();
            if (!cancelled) applyUser(null);
            return;
          }
          await new Promise((resolve) => setTimeout(resolve, 1000));
        }
      }
    };

    boot().finally(() => {
      if (!cancelled) setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [applyUser]);

  const completeLogin = useCallback(
    async (sessionId: string) => {
      setError(null);
      setSessionId(sessionId);
      try {
        const me = await fetchMe();
        applyUser(me);
      } catch (err) {
        clearSessionId();
        applyUser(null);
        const message = err instanceof ApiRequestError ? err.message : "Не удалось войти";
        setError(message);
        throw err;
      }
    },
    [applyUser],
  );

  const handleLogout = useCallback(() => {
    clearSessionId();
    applyUser(null);
    setError(null);
  }, [applyUser]);

  const value = useMemo(
    () => ({
      user,
      loading,
      error,
      isAuthenticated: user !== null,
      completeLogin,
      logout: handleLogout,
      refreshUser,
      clearError: () => setError(null),
    }),
    [user, loading, error, completeLogin, handleLogout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
