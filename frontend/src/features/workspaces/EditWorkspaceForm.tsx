"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { ErrorMessage } from "@/components/ErrorMessage";
import { useTenant } from "@/features/tenants/TenantProvider";
import { api } from "@/lib/api";
import type { AnswerMode, Tenant } from "@/lib/types";

export interface EditWorkspaceFormProps {
  tenant: Tenant;
  onDone: () => void;
}

export function EditWorkspaceForm({ tenant, onDone }: EditWorkspaceFormProps) {
  const t = useTranslations("tenants");
  const common = useTranslations("common");
  const { refreshTenants } = useTenant();
  const [name, setName] = useState(tenant.name);
  const [slug, setSlug] = useState(tenant.slug);
  const [defaultLocale, setDefaultLocale] = useState(tenant.default_locale);
  const [answerMode, setAnswerMode] = useState<AnswerMode>(tenant.answer_mode);
  const [isActive, setIsActive] = useState(tenant.is_active);
  const [error, setError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.tenants.update(tenant.id, {
        name,
        slug,
        default_locale: defaultLocale,
        answer_mode: answerMode,
        is_active: isActive,
      });
      await refreshTenants();
      onDone();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4 text-sm">
      <label className="flex flex-col gap-1">
        {t("name")}
        <input
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
          className="rounded border border-slate-300 px-3 py-2"
        />
      </label>
      <label className="flex flex-col gap-1">
        {t("slug")}
        <input
          required
          value={slug}
          onChange={(event) => setSlug(event.target.value)}
          className="rounded border border-slate-300 px-3 py-2"
        />
      </label>
      <label className="flex flex-col gap-1">
        {t("defaultLocale")}
        <select
          value={defaultLocale}
          onChange={(event) => setDefaultLocale(event.target.value)}
          className="rounded border border-slate-300 px-3 py-2"
        >
          <option value="it">Italiano</option>
          <option value="en">English</option>
        </select>
      </label>
      <label className="flex flex-col gap-1">
        {t("answerMode")}
        <select
          value={answerMode}
          onChange={(event) => setAnswerMode(event.target.value as AnswerMode)}
          className="rounded border border-slate-300 px-3 py-2"
        >
          <option value="strict">{t("strict")}</option>
          <option value="assistive">{t("assistive")}</option>
        </select>
      </label>
      <label className="flex flex-col gap-1">
        {t("status")}
        <select
          value={isActive ? "active" : "inactive"}
          onChange={(event) => setIsActive(event.target.value === "active")}
          className="rounded border border-slate-300 px-3 py-2"
        >
          <option value="active">{t("active")}</option>
          <option value="inactive">{t("inactive")}</option>
        </select>
      </label>
      <p className="-mt-2 text-xs text-slate-500">{t("statusHint")}</p>

      <ErrorMessage error={error} />
      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={saving}
          className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
        >
          {saving ? t("saving") : common("save")}
        </button>
        <button
          type="button"
          onClick={onDone}
          className="rounded border border-slate-300 px-4 py-2"
        >
          {common("cancel")}
        </button>
      </div>
    </form>
  );
}
