"use client";

import { useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/navigation";

const ROUTES: [RegExp, string][] = [
  [/^\/dashboard\/documents$/, "nav.documents"],
  [/^\/dashboard\/chat$/, "nav.chat"],
  [/^\/dashboard\/conversations$/, "nav.conversations"],
  [/^\/dashboard\/members$/, "nav.members"],
  [/^\/dashboard\/settings$/, "nav.settings"],
  [/^\/dashboard\/workspaces$/, "nav.workspaces"],
  [/^\/dashboard\/workspaces\/new$/, "tenants.new"],
  [/^\/dashboard\/workspaces\/[^/]+\/edit$/, "tenants.editTitle"],
];

export function Breadcrumbs() {
  const pathname = usePathname();
  const t = useTranslations();

  const match = ROUTES.find(([pattern]) => pattern.test(pathname));
  if (!match) return null;

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
          {t(match[1])}
        </li>
      </ol>
    </nav>
  );
}
