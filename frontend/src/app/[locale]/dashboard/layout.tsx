"use client";

import { Navbar } from "@/components/Navbar";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { RequireAuth } from "@/features/auth/RequireAuth";
import { OptionsMenu } from "@/features/navigation/OptionsMenu";
import { TenantProvider } from "@/features/tenants/TenantProvider";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <TenantProvider>
        <div className="min-h-screen">
          <Navbar>
            <OptionsMenu />
          </Navbar>
          <main className="mx-auto max-w-5xl px-4 py-8">
            <Breadcrumbs />
            <div className="mt-4">{children}</div>
          </main>
        </div>
      </TenantProvider>
    </RequireAuth>
  );
}
