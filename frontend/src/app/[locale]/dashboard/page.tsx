"use client";

import { DashboardOverview } from "@/features/home/DashboardOverview";
import { useWorkspace } from "@/features/workspaces/WorkspaceProvider";
import { NoWorkspaceGate } from "@/features/workspaces/NoWorkspaceGate";

export default function DashboardPage() {
  const { workspaces, loading } = useWorkspace();

  if (loading) {
    return <p className="text-slate-500">...</p>;
  }

  if (workspaces.length === 0) {
    return <NoWorkspaceGate />;
  }

  return <DashboardOverview />;
}
