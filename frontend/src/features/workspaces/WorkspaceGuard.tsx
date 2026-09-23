"use client";

import { useEffect } from "react";

import { useTenant } from "@/features/tenants/TenantProvider";
import { usePathname, useRouter } from "@/i18n/navigation";

const GUEST_ALLOWED_PATHS = ["/dashboard", "/dashboard/workspaces/new"];

export function WorkspaceGuard({ children }: { children: React.ReactNode }) {
  const { tenants, loading } = useTenant();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (loading || tenants.length > 0) return;
    if (!GUEST_ALLOWED_PATHS.includes(pathname)) {
      router.replace("/dashboard");
    }
  }, [loading, tenants, pathname, router]);

  return <>{children}</>;
}
