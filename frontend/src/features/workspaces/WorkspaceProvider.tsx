"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { useAuth } from "@/features/auth/AuthProvider";
import { activeWorkspaceStore } from "@/lib/active-workspace-store";
import { api } from "@/lib/api";
import type { Workspace } from "@/lib/types";

interface WorkspaceContextValue {
  workspaces: Workspace[];
  activeWorkspace: Workspace | null;
  loading: boolean;
  selectWorkspace: (workspaceId: number) => void;
  refreshWorkspaces: () => Promise<void>;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshWorkspaces = useCallback(async () => {
    try {
      const list = await api.workspaces.list();
      setWorkspaces(list);
      const stored = activeWorkspaceStore.get();
      const next = list.find((workspace) => workspace.id === stored) ?? list[0] ?? null;
      if (next) {
        activeWorkspaceStore.set(next.id);
        setActiveWorkspaceId(next.id);
      } else {
        setActiveWorkspaceId(null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!user) {
      setWorkspaces([]);
      setActiveWorkspaceId(null);
      setLoading(false);
      return;
    }
    void refreshWorkspaces();
  }, [user, refreshWorkspaces]);

  const selectWorkspace = useCallback((workspaceId: number) => {
    activeWorkspaceStore.set(workspaceId);
    setActiveWorkspaceId(workspaceId);
  }, []);

  const activeWorkspace = workspaces.find((workspace) => workspace.id === activeWorkspaceId) ?? null;

  return (
    <WorkspaceContext.Provider
      value={{ workspaces, activeWorkspace, loading, selectWorkspace, refreshWorkspaces }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace(): WorkspaceContextValue {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error("useWorkspace must be used within a WorkspaceProvider");
  }
  return context;
}
