"use client";

import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";

export function HomeContent() {
  const t = useTranslations("home");

  return (
    <main className="mx-auto flex max-w-3xl flex-col items-start gap-6 px-4 py-24">
      <h1 className="text-4xl font-semibold">{t("title")}</h1>
      <p className="text-lg text-slate-600">{t("subtitle")}</p>
      <Link
        href="/dashboard"
        className="rounded bg-slate-900 px-5 py-2.5 text-white hover:bg-slate-800"
      >
        {t("cta")}
      </Link>
    </main>
  );
}
