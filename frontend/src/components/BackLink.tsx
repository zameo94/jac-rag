"use client";

import { useTranslations } from "next-intl";

import { ArrowLeftIcon } from "@/components/icons";
import { Link } from "@/i18n/navigation";

const CLASSES =
  "inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900";

export function BackLink({ href }: { href: string }) {
  const t = useTranslations("common");

  return (
    <Link href={href} className={CLASSES}>
      <ArrowLeftIcon className="h-4 w-4" />
      {t("back")}
    </Link>
  );
}

export function BackButton({ onClick }: { onClick: () => void }) {
  const t = useTranslations("common");

  return (
    <button type="button" onClick={onClick} className={CLASSES}>
      <ArrowLeftIcon className="h-4 w-4" />
      {t("back")}
    </button>
  );
}
