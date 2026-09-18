"use client";

import { useEffect } from "react";

import { DocumentsPanel } from "@/features/documents/DocumentsPanel";
import { useTenant } from "@/features/tenants/TenantProvider";
import { useRouter } from "@/i18n/navigation";

export default function DashboardPage() {
  const { activeTenant, loading, tenants } = useTenant();
  const router = useRouter();

  useEffect(() => {
    if (!loading && tenants.length === 0) {
      router.replace("/onboarding");
    }
  }, [loading, tenants, router]);

  if (loading || !activeTenant) {
    return <p className="text-slate-500">...</p>;
  }

  return <DocumentsPanel />;
}
