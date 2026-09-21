"use client";

import { useTranslations } from "next-intl";

import { LlmSettingsPanel } from "@/features/llm/LlmSettingsPanel";
import { useTenant } from "@/features/tenants/TenantProvider";

export default function SettingsPage() {
  const t = useTranslations("settings");
  const tenantsT = useTranslations("tenants");
  const { activeTenant } = useTenant();

  if (!activeTenant) return null;

  return (
    <section className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">{t("title")}</h1>
      <div className="rounded border border-slate-200 bg-white p-4 text-sm">
        <p className="text-slate-500">{tenantsT("answerMode")}</p>
        <p className="font-medium">
          {activeTenant.answer_mode === "strict"
            ? tenantsT("strict")
            : tenantsT("assistive")}
        </p>
      </div>
      <LlmSettingsPanel />
    </section>
  );
}
