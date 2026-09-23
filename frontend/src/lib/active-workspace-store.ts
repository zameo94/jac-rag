const ACTIVE_WORKSPACE_KEY = "jacrag_active_workspace";

function hasStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export const activeWorkspaceStore = {
  get(): number | null {
    if (!hasStorage()) return null;
    const raw = window.localStorage.getItem(ACTIVE_WORKSPACE_KEY);
    if (!raw) return null;
    const parsed = Number.parseInt(raw, 10);
    return Number.isNaN(parsed) ? null : parsed;
  },
  set(workspaceId: number): void {
    if (!hasStorage()) return;
    window.localStorage.setItem(ACTIVE_WORKSPACE_KEY, String(workspaceId));
  },
  clear(): void {
    if (!hasStorage()) return;
    window.localStorage.removeItem(ACTIVE_WORKSPACE_KEY);
  },
};
