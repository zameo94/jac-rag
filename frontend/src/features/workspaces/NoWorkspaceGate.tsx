"use client";

import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";

export function NoWorkspaceGate() {
  const t = useTranslations("tenants");

  return (
    <section className="mx-auto flex max-w-lg flex-col items-center gap-4 py-16 text-center">
      <h1 className="text-2xl font-semibold">{t("noneTitle")}</h1>
      <p className="text-slate-600">{t("noneHint")}</p>
      <Link
        href="/dashboard/workspaces/new"
        className="rounded bg-slate-900 px-5 py-2.5 text-white hover:bg-slate-800"
      >
        {t("noneCta")}
      </Link>
    </section>
  );
}
