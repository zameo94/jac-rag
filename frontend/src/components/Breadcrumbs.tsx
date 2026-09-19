"use client";

import { useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/navigation";

const ROUTE_LABELS: Record<string, string> = {
  "/dashboard": "nav.documents",
  "/dashboard/members": "nav.members",
  "/dashboard/settings": "nav.settings",
};

export function Breadcrumbs() {
  const pathname = usePathname();
  const t = useTranslations();

  const currentLabel = ROUTE_LABELS[pathname];
  if (!currentLabel) return null;

  return (
    <nav aria-label={t("breadcrumbs.label")}>
      <ol className="flex items-center gap-2 text-sm text-slate-500">
        <li>
          <Link href="/" className="hover:text-slate-900 hover:underline">
            {t("nav.home")}
          </Link>
        </li>
        <li aria-hidden="true">/</li>
        <li aria-current="page" className="font-medium text-slate-900">
          {t(currentLabel)}
        </li>
      </ol>
    </nav>
  );
}
