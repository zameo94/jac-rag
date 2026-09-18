"use client";

import { useTranslations } from "next-intl";

import { useTenant } from "@/features/tenants/TenantProvider";

export function TenantSwitcher() {
  const t = useTranslations("tenants");
  const { tenants, activeTenant, selectTenant } = useTenant();

  if (tenants.length === 0) return null;

  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="text-slate-500">{t("switch")}</span>
      <select
        aria-label={t("switch")}
        value={activeTenant?.id ?? ""}
        onChange={(event) => selectTenant(Number(event.target.value))}
        className="rounded border border-slate-300 bg-white px-2 py-1"
      >
        {tenants.map((tenant) => (
          <option key={tenant.id} value={tenant.id}>
            {tenant.name}
          </option>
        ))}
      </select>
    </label>
  );
}
