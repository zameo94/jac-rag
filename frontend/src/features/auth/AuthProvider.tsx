"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { isApiError } from "@/lib/api-error";
import { tokenStore } from "@/lib/token-store";
import type { User } from "@/lib/types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, locale: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const refreshUser = useCallback(async () => {
    if (!tokenStore.getAccess()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.auth.me();
      setUser(me);
    } catch (error) {
      if (isApiError(error) && (error.status === 401 || error.status === 403)) {
        tokenStore.clear();
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
      const tokens = await api.auth.login(email, password);
      tokenStore.set(tokens.access_token, tokens.refresh_token);
      const me = await api.auth.me();
      setUser(me);
      router.push(`/dashboard`);
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

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
    router.push(`/login`);
  }, [router]);

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
