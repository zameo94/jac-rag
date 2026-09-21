"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { ErrorMessage } from "@/components/ErrorMessage";
import { useAuth } from "@/features/auth/AuthProvider";
import { useTenant } from "@/features/tenants/TenantProvider";
import { api } from "@/lib/api";
import type {
  LLMConfig,
  LLMSettings,
  LLMSettingsUpdate,
  MembershipRole,
} from "@/lib/types";

export function LlmSettingsPanel() {
  const t = useTranslations("settings");
  const { activeTenant } = useTenant();
  const { user } = useAuth();
  const [config, setConfig] = useState<LLMConfig | null>(null);
  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [role, setRole] = useState<MembershipRole | null>(null);
  const [allowed, setAllowed] = useState<string[]>([]);
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [unlockKey, setUnlockKey] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);

  const tenantId = activeTenant?.id ?? null;
  const isAdmin = role === "OWNER" || role === "ADMIN";
  const hasStoredKey = settings?.external_configured ?? false;
  const editableKey = unlockKey || !hasStoredKey;

  const load = useCallback(async () => {
    if (!tenantId) return;
    try {
      const configuration = await api.llm.config(tenantId);
      setConfig(configuration);
      setError(null);

      const members = await api.members.list(tenantId);
      const me = members.find((member) => member.user_id === user?.id);
      setRole(me?.role ?? null);

      if (me && (me.role === "OWNER" || me.role === "ADMIN")) {
        const current = await api.llm.settings(tenantId);
        setSettings(current);
        setAllowed(current.allowed_providers);
        setBaseUrl(current.external_base_url ?? "");
        setModel(current.external_model ?? "");
      }
    } catch (err) {
      setError(err);
    }
  }, [tenantId, user?.id]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!tenantId || !config) return null;

  const available = config.providers.filter(
    (provider) => provider.enabled && config.allowed_providers.includes(provider.id),
  );

  async function selectProvider(providerId: string) {
    if (!tenantId) return;
    try {
      await api.llm.selectProvider(tenantId, providerId);
      setConfig((current) =>
        current ? { ...current, selected_provider: providerId } : current,
      );
    } catch (err) {
      setError(err);
    }
  }

  function toggleAllowed(providerId: string) {
    setAllowed((current) =>
      current.includes(providerId)
        ? current.filter((id) => id !== providerId)
        : [...current, providerId],
    );
  }

  async function save() {
    if (!tenantId) return;
    setSaving(true);
    try {
      const body: LLMSettingsUpdate = { allowed_providers: allowed };
      if (baseUrl && model) {
        body.external_base_url = baseUrl;
        body.external_model = model;
      }
      if (apiKey) {
        body.external_api_key = apiKey;
      }
      const updated = await api.llm.updateSettings(tenantId, body);
      setSettings(updated);
      setApiKey("");
      setUnlockKey(false);
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="flex flex-col gap-6">
      <h2 className="text-lg font-semibold">{t("title")}</h2>
      <ErrorMessage error={error} />

      <div className="flex flex-col gap-2 rounded border border-slate-200 bg-white p-4 text-sm">
        <p className="font-medium">{t("usedProvider")}</p>
        {available.length === 0 ? (
          <p className="text-slate-500">{t("noProviders")}</p>
        ) : (
          available.map((provider) => (
            <label key={provider.id} className="flex items-center gap-2">
              <input
                type="radio"
                name="llm-provider"
                checked={config.selected_provider === provider.id}
                onChange={() => selectProvider(provider.id)}
              />
              <span>{t(`providers.${provider.id}`)}</span>
              {provider.models.length > 0 && (
                <span className="text-xs text-slate-500">
                  {provider.models.join(", ")}
                </span>
              )}
            </label>
          ))
        )}
      </div>

      {isAdmin && (
        <div className="flex flex-col gap-4 rounded border border-slate-200 bg-white p-4 text-sm">
          <div className="flex flex-col gap-2">
            <p className="font-medium">{t("allowedProviders")}</p>
            {config.providers.map((provider) => (
              <label key={provider.id} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={allowed.includes(provider.id)}
                  onChange={() => toggleAllowed(provider.id)}
                />
                <span>{t(`providers.${provider.id}`)}</span>
              </label>
            ))}
          </div>

          <div className="flex flex-col gap-2">
            <p className="font-medium">
              {t("externalSection")}{" "}
              <span
                className={
                  settings?.external_configured
                    ? "text-green-700"
                    : "text-slate-500"
                }
              >
                {settings?.external_configured
                  ? t("externalConfigured")
                  : t("externalNotConfigured")}
              </span>
            </p>
            <input
              className="rounded border border-slate-300 px-2 py-1"
              placeholder={t("baseUrl")}
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
            />
            <input
              className="rounded border border-slate-300 px-2 py-1"
              placeholder={t("model")}
              value={model}
              onChange={(event) => setModel(event.target.value)}
            />
            {editableKey ? (
              <input
                className="rounded border border-slate-300 px-2 py-1"
                type="password"
                placeholder={t("apiKey")}
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
              />
            ) : (
              <input
                className="rounded border border-slate-200 bg-slate-50 px-2 py-1 text-slate-500"
                type="text"
                value={"*".repeat(12)}
                readOnly
                disabled
              />
            )}
            {hasStoredKey && (
              <label className="flex items-center gap-2 text-xs text-slate-600">
                <input
                  type="checkbox"
                  checked={unlockKey}
                  onChange={(event) => {
                    setUnlockKey(event.target.checked);
                    if (!event.target.checked) setApiKey("");
                  }}
                />
                {t("editKey")}
              </label>
            )}
            <span className="text-xs text-slate-500">{t("apiKeyHint")}</span>
          </div>

          <button
            type="button"
            onClick={save}
            disabled={saving}
            className="self-start rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
          >
            {saving ? t("saving") : t("save")}
          </button>
        </div>
      )}
    </section>
  );
}
