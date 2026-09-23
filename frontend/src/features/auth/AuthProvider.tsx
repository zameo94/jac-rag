"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { isApiError } from "@/lib/api-error";
import { activeWorkspaceStore } from "@/lib/active-workspace-store";
import {
  SESSION_IDLE_TIMEOUT_MS,
  useSessionIdle,
} from "@/lib/session-idle";
import type { User } from "@/lib/types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, locale: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const refreshUser = useCallback(async () => {
    try {
      setUser(await api.auth.me());
    } catch (error) {
      if (isApiError(error) && error.status === 401) {
        try {
          setUser(await api.auth.refresh());
        } catch {
          setUser(null);
        }
      } else if (isApiError(error) && error.status === 403) {
        setUser(null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshUser();
  }, [refreshUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      const loggedIn = await api.auth.login(email, password);
      setUser(loggedIn);
      router.push("/");
    },
    [router],
  );

  const register = useCallback(
    async (email: string, password: string, locale: string) => {
      await api.auth.register(email, password, locale);
      await login(email, password);
    },
    [login],
  );

  const logout = useCallback(async () => {
    try {
      await api.auth.logout();
    } catch {
      // ignore: cookies are cleared client-side by the redirect below
    }
    activeWorkspaceStore.clear();
    setUser(null);
    router.push("/login");
  }, [router]);

  useSessionIdle({
    enabled: user !== null && SESSION_IDLE_TIMEOUT_MS > 0,
    onIdle: logout,
  });

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
