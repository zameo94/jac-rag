"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { ErrorMessage } from "@/components/ErrorMessage";
import { PencilIcon, TrashIcon } from "@/components/icons";
import { useTenant } from "@/features/tenants/TenantProvider";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";
import type { MembershipRole, Tenant } from "@/lib/types";

export function WorkspacesPanel() {
  const t = useTranslations("tenants");
  const { tenants, activeTenant, selectTenant, refreshTenants } = useTenant();
  const [roles, setRoles] = useState<Record<number, MembershipRole>>({});
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let mounted = true;
    void Promise.all(
      tenants.map((tenant) =>
        api.members
          .me(tenant.id)
          .then((membership) => [tenant.id, membership.role] as const)
          .catch(() => null),
      ),
    ).then((entries) => {
      if (!mounted) return;
      const next: Record<number, MembershipRole> = {};
      for (const entry of entries) {
        if (entry) next[entry[0]] = entry[1];
      }
      setRoles(next);
    });
    return () => {
      mounted = false;
    };
  }, [tenants]);

  function canManage(tenantId: number): boolean {
    const role = roles[tenantId];
    return role === "OWNER" || role === "ADMIN";
  }

  async function handleDelete(tenant: Tenant) {
    if (!window.confirm(t("deleteConfirm"))) return;
    setError(null);
    try {
      await api.tenants.remove(tenant.id);
      await refreshTenants();
    } catch (err) {
      setError(err);
    }
  }

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <Link
          href="/dashboard/workspaces/new"
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white hover:bg-slate-800"
        >
          {t("new")}
        </Link>
      </div>

      <ErrorMessage error={error} />

      {tenants.length === 0 ? (
        <p className="text-slate-500">{t("empty")}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {tenants.map((tenant) => (
            <li
              key={tenant.id}
              className="flex items-center justify-between rounded border border-slate-200 bg-white p-3 text-sm"
            >
              <span>
                <span className="font-medium">{tenant.name}</span>{" "}
                <span className="text-slate-400">{tenant.slug}</span>
              </span>
              <span className="flex items-center gap-3">
                <span
                  className={`rounded px-2 py-0.5 text-xs ${
                    tenant.is_active
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-slate-100 text-slate-500"
                  }`}
                >
                  {tenant.is_active ? t("active") : t("inactive")}
                </span>
                {tenant.id === activeTenant?.id ? (
                  <span className="text-xs text-slate-500">{t("current")}</span>
                ) : (
                  <button
                    type="button"
                    onClick={() => selectTenant(tenant.id)}
                    className="text-xs underline"
                  >
                    {t("switch")}
                  </button>
                )}
                {canManage(tenant.id) && (
                  <Link
                    href={`/dashboard/workspaces/${tenant.id}/edit`}
                    aria-label={t("edit")}
                    className="text-slate-500 hover:text-slate-900"
                  >
                    <PencilIcon className="h-4 w-4" />
                  </Link>
                )}
                {roles[tenant.id] === "OWNER" && (
                  <button
                    type="button"
                    aria-label={t("delete")}
                    onClick={() => handleDelete(tenant)}
                    className="text-red-600 hover:text-red-700"
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
