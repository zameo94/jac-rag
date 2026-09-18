"use client";

import { useTranslations } from "next-intl";

import { isApiError } from "@/lib/api-error";

export function ErrorMessage({ error }: { error: unknown }) {
  const t = useTranslations("errors");

  if (!error) return null;

  let message = t("generic");
  if (isApiError(error)) {
    message = t.has(error.code) ? t(error.code) : t("generic");
  }

  return (
    <p role="alert" className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">
      {message}
    </p>
  );
}
