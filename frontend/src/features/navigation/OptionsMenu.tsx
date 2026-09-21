"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import { MenuIcon } from "@/components/icons";
import { useAuth } from "@/features/auth/AuthProvider";
import { useTenant } from "@/features/tenants/TenantProvider";
import { Link, usePathname } from "@/i18n/navigation";

export function OptionsMenu() {
  const t = useTranslations("nav");
  const auth = useTranslations("auth");
  const tenantsLabels = useTranslations("tenants");
  const { logout } = useAuth();
  const { tenants, activeTenant, selectTenant } = useTenant();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    function handlePointerDown(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  const links = [
    { href: "/dashboard", label: t("documents") },
    { href: "/dashboard/playground", label: t("playground") },
    { href: "/dashboard/conversations", label: t("conversations") },
    { href: "/dashboard/members", label: t("members") },
    { href: "/dashboard/settings", label: t("settings") },
  ];

  function close() {
    setOpen(false);
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t("menu")}
        onClick={() => setOpen((value) => !value)}
        className="flex items-center gap-2 rounded border border-slate-300 bg-white px-2 py-1 text-sm"
      >
        <MenuIcon className="h-4 w-4" />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 w-56 overflow-hidden rounded border border-slate-200 bg-white py-1 shadow-lg"
        >
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              role="menuitem"
              aria-current={pathname === link.href}
              onClick={close}
              className={`block px-3 py-1.5 text-sm hover:bg-slate-50 ${
                pathname === link.href ? "font-medium" : ""
              }`}
            >
              {link.label}
            </Link>
          ))}

          {tenants.length > 0 && (
            <div className="mt-1 border-t border-slate-100 pt-1">
              <p className="px-3 py-1 text-xs uppercase tracking-wide text-slate-400">
                {tenantsLabels("switch")}
              </p>
              {tenants.map((tenant) => (
                <button
                  key={tenant.id}
                  type="button"
                  role="menuitemradio"
                  aria-checked={tenant.id === activeTenant?.id}
                  onClick={() => {
                    selectTenant(tenant.id);
                    close();
                  }}
                  className={`flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-slate-50 ${
                    tenant.id === activeTenant?.id ? "font-medium" : ""
                  }`}
                >
                  <span
                    aria-hidden="true"
                    className={`h-1.5 w-1.5 rounded-full ${
                      tenant.id === activeTenant?.id ? "bg-slate-900" : "bg-transparent"
                    }`}
                  />
                  {tenant.name}
                </button>
              ))}
            </div>
          )}

          <div className="mt-1 border-t border-slate-100 pt-1">
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                close();
                logout();
              }}
              className="block w-full px-3 py-1.5 text-left text-sm text-red-600 hover:bg-slate-50"
            >
              {auth("logout")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
