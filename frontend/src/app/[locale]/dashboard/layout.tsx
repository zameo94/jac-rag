"use client";

import { Navbar } from "@/components/Navbar";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { RequireAuth } from "@/features/auth/RequireAuth";
import { OptionsMenu } from "@/features/navigation/OptionsMenu";
import { WorkspaceProvider } from "@/features/workspaces/WorkspaceProvider";
import { WorkspaceGuard } from "@/features/workspaces/WorkspaceGuard";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <WorkspaceProvider>
        <WorkspaceGuard>
          <div className="min-h-screen">
            <Navbar>
              <OptionsMenu />
            </Navbar>
            <main className="mx-auto max-w-5xl px-4 py-8">
              <Breadcrumbs />
              <div className="mt-4">{children}</div>
            </main>
          </div>
        </WorkspaceGuard>
      </WorkspaceProvider>
    </RequireAuth>
  );
}
