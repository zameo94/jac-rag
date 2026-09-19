const ACTIVE_TENANT_KEY = "jacrag_active_tenant";

function hasStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

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
