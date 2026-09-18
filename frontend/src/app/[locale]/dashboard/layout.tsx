"use client";

import { useEffect } from "react";

import { Breadcrumbs } from "@/components/Breadcrumbs";
import { Navbar } from "@/components/Navbar";
import { useAuth } from "@/features/auth/AuthProvider";
import { OptionsMenu } from "@/features/navigation/OptionsMenu";
import { TenantProvider } from "@/features/tenants/TenantProvider";
import { useRouter } from "@/i18n/navigation";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [loading, user, router]);

  if (loading || !user) {
    return <p className="p-8 text-slate-500">...</p>;
  }

  return (
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
  );
}
