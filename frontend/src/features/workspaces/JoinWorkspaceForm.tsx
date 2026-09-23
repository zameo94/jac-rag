"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { ErrorMessage } from "@/components/ErrorMessage";
import { useTenant } from "@/features/tenants/TenantProvider";
import { useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";

export function JoinWorkspaceForm() {
  const t = useTranslations("tenants");
  const router = useRouter();
  const { refreshTenants } = useTenant();
  const [code, setCode] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.invitations.accept(code.trim());
      await refreshTenants();
      router.push("/");
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
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
  );
}
