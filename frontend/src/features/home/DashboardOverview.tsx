"use client";

import { useTranslations } from "next-intl";

import {
  ChatIcon,
  ConversationsIcon,
  DocumentsIcon,
  MembersIcon,
  SettingsIcon,
  WorkspacesIcon,
} from "@/components/icons";
import { Link } from "@/i18n/navigation";

const CARDS = [
  { href: "/dashboard/documents", key: "documents", Icon: DocumentsIcon },
  { href: "/dashboard/chat", key: "chat", Icon: ChatIcon },
  { href: "/dashboard/conversations", key: "conversations", Icon: ConversationsIcon },
  { href: "/dashboard/members", key: "members", Icon: MembersIcon },
  { href: "/dashboard/settings", key: "settings", Icon: SettingsIcon },
  { href: "/dashboard/workspaces", key: "workspaces", Icon: WorkspacesIcon },
] as const;

export function DashboardOverview() {
  const t = useTranslations("overview");

  return (
    <section className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="mt-1 text-slate-600">{t("subtitle")}</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {CARDS.map((card) => (
          <Link
            key={card.key}
            href={card.href}
            className="group flex flex-col gap-3 rounded border border-slate-200 bg-white p-4 transition hover:border-slate-400 hover:shadow-sm"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 text-slate-700 transition group-hover:bg-slate-900 group-hover:text-white">
              <card.Icon className="h-5 w-5" />
            </span>
            <span>
              <span className="block font-medium">{t(card.key)}</span>
              <span className="mt-1 block text-sm text-slate-500">
                {t(`${card.key}Hint`)}
              </span>
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
