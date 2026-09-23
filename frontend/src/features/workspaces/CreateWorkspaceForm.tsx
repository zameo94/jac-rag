"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { ErrorMessage } from "@/components/ErrorMessage";
import { useWorkspace } from "@/features/workspaces/WorkspaceProvider";
import { useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import type { AnswerMode } from "@/lib/types";

export function CreateWorkspaceForm() {
  const t = useTranslations("workspaces");
  const locale = useLocale();
  const router = useRouter();
  const { refreshWorkspaces, selectWorkspace } = useWorkspace();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [defaultLocale, setDefaultLocale] = useState(locale);
  const [answerMode, setAnswerMode] = useState<AnswerMode>("strict");
  const [error, setError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const created = await api.workspaces.create(name, slug, defaultLocale, answerMode);
      await refreshWorkspaces();
      selectWorkspace(created.id);
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
        {t("name")}
        <input
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
          className="rounded border border-slate-300 px-3 py-2"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        {t("slug")}
        <input
          value={slug}
          placeholder={t("slugPlaceholder")}
          onChange={(event) => setSlug(event.target.value)}
          className="rounded border border-slate-300 px-3 py-2"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
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
      <label className="flex flex-col gap-1 text-sm">
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
      <ErrorMessage error={error} />
      <button
        type="submit"
        disabled={submitting}
        className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
      >
        {t("createCta")}
      </button>
    </form>
  );
}
