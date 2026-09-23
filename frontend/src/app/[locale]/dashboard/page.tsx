"use client";

import { DashboardOverview } from "@/features/home/DashboardOverview";
import { useTenant } from "@/features/tenants/TenantProvider";
import { NoWorkspaceGate } from "@/features/workspaces/NoWorkspaceGate";

export default function DashboardPage() {
  const { tenants, loading } = useTenant();

  if (loading) {
    return <p className="text-slate-500">...</p>;
  }

  if (tenants.length === 0) {
    return <NoWorkspaceGate />;
  }

  return <DashboardOverview />;
}
