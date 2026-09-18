"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";

import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { useAuth } from "@/features/auth/AuthProvider";
import { TenantProvider } from "@/features/tenants/TenantProvider";
import { TenantSwitcher } from "@/features/tenants/TenantSwitcher";
import { Link, usePathname, useRouter } from "@/i18n/navigation";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const t = useTranslations("nav");
  const auth = useTranslations("auth");
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [loading, user, router]);

  if (loading || !user) {
    return <p className="p-8 text-slate-500">...</p>;
  }

  const links = [
    { href: "/dashboard", label: t("documents") },
    { href: "/dashboard/members", label: t("members") },
    { href: "/dashboard/settings", label: t("settings") },
  ];

  return (
    <TenantProvider>
      <div className="min-h-screen">
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-4 py-3">
            <div className="flex items-center gap-6">
              <span className="font-semibold">jac-rag</span>
              <nav className="flex items-center gap-4 text-sm">
                {links.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={
                      pathname === link.href
                        ? "font-medium text-slate-900"
                        : "text-slate-500 hover:text-slate-900"
                    }
                  >
                    {link.label}
                  </Link>
                ))}
              </nav>
            </div>
            <div className="flex items-center gap-3">
              <TenantSwitcher />
              <LocaleSwitcher />
              <button
                type="button"
                onClick={logout}
                className="rounded border border-slate-300 px-3 py-1 text-sm"
              >
                {auth("logout")}
              </button>
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
      </div>
    </TenantProvider>
  );
}
