"use client";

import { useTranslations } from "next-intl";

import { EmbedKeysPanel } from "@/features/embed-keys/EmbedKeysPanel";
import { LlmSettingsPanel } from "@/features/llm/LlmSettingsPanel";

export default function SettingsPage() {
  const t = useTranslations("settings");

  return (
    <section className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">{t("pageTitle")}</h1>
      <LlmSettingsPanel />
      <EmbedKeysPanel />
    </section>
  );
}
