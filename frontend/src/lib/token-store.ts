const ACCESS_TOKEN_KEY = "jacrag_access_token";
const REFRESH_TOKEN_KEY = "jacrag_refresh_token";
const ACTIVE_TENANT_KEY = "jacrag_active_tenant";

function hasStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export const tokenStore = {
  getAccess(): string | null {
    if (!hasStorage()) return null;
    return window.localStorage.getItem(ACCESS_TOKEN_KEY);
  },
  getRefresh(): string | null {
    if (!hasStorage()) return null;
    return window.localStorage.getItem(REFRESH_TOKEN_KEY);
  },
  set(access: string, refresh: string): void {
    if (!hasStorage()) return;
    window.localStorage.setItem(ACCESS_TOKEN_KEY, access);
    window.localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
  },
  clear(): void {
    if (!hasStorage()) return;
    window.localStorage.removeItem(ACCESS_TOKEN_KEY);
    window.localStorage.removeItem(REFRESH_TOKEN_KEY);
    window.localStorage.removeItem(ACTIVE_TENANT_KEY);
  },
};

export const activeTenantStore = {
  get(): number | null {
    if (!hasStorage()) return null;
    const raw = window.localStorage.getItem(ACTIVE_TENANT_KEY);
    if (!raw) return null;
    const parsed = Number.parseInt(raw, 10);
    return Number.isNaN(parsed) ? null : parsed;
  },
  set(tenantId: number): void {
    if (!hasStorage()) return;
    window.localStorage.setItem(ACTIVE_TENANT_KEY, String(tenantId));
  },
  clear(): void {
    if (!hasStorage()) return;
    window.localStorage.removeItem(ACTIVE_TENANT_KEY);
  },
};
