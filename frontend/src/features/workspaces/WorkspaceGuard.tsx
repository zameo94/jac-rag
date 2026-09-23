"use client";

import { useEffect } from "react";

import { useWorkspace } from "@/features/workspaces/WorkspaceProvider";
import { usePathname, useRouter } from "@/i18n/navigation";

const GUEST_ALLOWED_PATHS = ["/dashboard", "/dashboard/workspaces/new"];

export function WorkspaceGuard({ children }: { children: React.ReactNode }) {
  const { workspaces, loading } = useWorkspace();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (loading || workspaces.length > 0) return;
    if (!GUEST_ALLOWED_PATHS.includes(pathname)) {
      router.replace("/dashboard");
    }
  }, [loading, workspaces, pathname, router]);

  return <>{children}</>;
}
