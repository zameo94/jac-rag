"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { ErrorMessage } from "@/components/ErrorMessage";
import { useTenant } from "@/features/tenants/TenantProvider";
import { useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";

export function OnboardingPanel() {
  const t = useTranslations("onboarding");
  const locale = useLocale();
  const router = useRouter();
  const { refreshTenants } = useTenant();
  const [tab, setTab] = useState<"create" | "join">("create");
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.tenants.create(name, slug, locale);
      await refreshTenants();
      router.push("/dashboard");
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleJoin(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.invitations.accept(code.trim());
      await refreshTenants();
      router.push("/dashboard");
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <h1 className="text-2xl font-semibold">{t("title")}</h1>
      <p className="mt-2 text-sm text-slate-600">{t("subtitle")}</p>

      <div className="mt-6 flex gap-2">
        <button
          type="button"
          onClick={() => setTab("create")}
          className={`rounded px-3 py-1 text-sm ${
            tab === "create" ? "bg-slate-900 text-white" : "bg-slate-200"
          }`}
        >
          {t("createTenant")}
        </button>
        <button
          type="button"
          onClick={() => setTab("join")}
          className={`rounded px-3 py-1 text-sm ${
            tab === "join" ? "bg-slate-900 text-white" : "bg-slate-200"
          }`}
        >
          {t("joinWithCode")}
        </button>
      </div>

      {tab === "create" ? (
        <form onSubmit={handleCreate} className="mt-4 flex flex-col gap-4">
          <label className="flex flex-col gap-1 text-sm">
            {t("tenantName")}
            <input
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="rounded border border-slate-300 px-3 py-2"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            {t("tenantSlug")}
            <input
              value={slug}
              onChange={(event) => setSlug(event.target.value)}
              className="rounded border border-slate-300 px-3 py-2"
            />
          </label>
          <ErrorMessage error={error} />
          <button
            type="submit"
            disabled={submitting}
            className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
          >
            {t("createCta")}
          </button>
        </form>
      ) : (
        <form onSubmit={handleJoin} className="mt-4 flex flex-col gap-4">
          <label className="flex flex-col gap-1 text-sm">
            {t("inviteCode")}
            <input
              required
              value={code}
              onChange={(event) => setCode(event.target.value)}
              className="rounded border border-slate-300 px-3 py-2"
            />
          </label>
          <ErrorMessage error={error} />
          <button
            type="submit"
            disabled={submitting}
            className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
          >
            {t("acceptCta")}
          </button>
        </form>
      )}
    </div>
  );
}
