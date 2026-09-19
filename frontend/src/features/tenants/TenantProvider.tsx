"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { useAuth } from "@/features/auth/AuthProvider";
import { activeTenantStore } from "@/lib/active-tenant-store";
import { api } from "@/lib/api";
import type { Tenant } from "@/lib/types";

interface TenantContextValue {
  tenants: Tenant[];
  activeTenant: Tenant | null;
  loading: boolean;
  selectTenant: (tenantId: number) => void;
  refreshTenants: () => Promise<void>;
}

const TenantContext = createContext<TenantContextValue | null>(null);

export function TenantProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [activeTenantId, setActiveTenantId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshTenants = useCallback(async () => {
    try {
      const list = await api.tenants.list();
      setTenants(list);
      const stored = activeTenantStore.get();
      const next = list.find((tenant) => tenant.id === stored) ?? list[0] ?? null;
      if (next) {
        activeTenantStore.set(next.id);
        setActiveTenantId(next.id);
      } else {
        setActiveTenantId(null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!user) {
      setTenants([]);
      setActiveTenantId(null);
      setLoading(false);
      return;
    }
    void refreshTenants();
  }, [user, refreshTenants]);

  const selectTenant = useCallback((tenantId: number) => {
    activeTenantStore.set(tenantId);
    setActiveTenantId(tenantId);
  }, []);

  const activeTenant = tenants.find((tenant) => tenant.id === activeTenantId) ?? null;

  return (
    <TenantContext.Provider
      value={{ tenants, activeTenant, loading, selectTenant, refreshTenants }}
    >
      {children}
    </TenantContext.Provider>
  );
}

export function useTenant(): TenantContextValue {
  const context = useContext(TenantContext);
  if (!context) {
    throw new Error("useTenant must be used within a TenantProvider");
  }
  return context;
}
