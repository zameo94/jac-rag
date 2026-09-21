"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { ErrorMessage } from "@/components/ErrorMessage";
import { useAuth } from "@/features/auth/AuthProvider";
import { useTenant } from "@/features/tenants/TenantProvider";
import { api } from "@/lib/api";
import type { ApiKey, MembershipRole } from "@/lib/types";

export function EmbedKeysPanel() {
  const t = useTranslations("embedKeys");
  const common = useTranslations("common");
  const { activeTenant } = useTenant();
  const { user } = useAuth();
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [role, setRole] = useState<MembershipRole | null>(null);
  const [name, setName] = useState("");
  const [created, setCreated] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const tenantId = activeTenant?.id ?? null;
  const isAdmin = role === "OWNER" || role === "ADMIN";

  const load = useCallback(async () => {
    if (!tenantId) return;
    try {
      const members = await api.members.list(tenantId);
      const me = members.find((member) => member.user_id === user?.id);
      setRole(me?.role ?? null);
      if (me && (me.role === "OWNER" || me.role === "ADMIN")) {
        setKeys(await api.apiKeys.list(tenantId));
      }
      setError(null);
    } catch (err) {
      setError(err);
    }
  }, [tenantId, user?.id]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!tenantId || !isAdmin) return null;

  async function create() {
    if (!tenantId || !name.trim()) return;
    try {
      const key = await api.apiKeys.create(tenantId, name.trim());
      setCreated(key.key);
      setCopied(false);
      setName("");
      await load();
    } catch (err) {
      setError(err);
    }
  }

  async function toggle(key: ApiKey) {
    if (!tenantId) return;
    try {
      await api.apiKeys.setActive(tenantId, key.id, !key.is_active);
      await load();
    } catch (err) {
      setError(err);
    }
  }

  async function copy() {
    if (!created) return;
    await navigator.clipboard.writeText(created);
    setCopied(true);
  }

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold">{t("title")}</h2>
      <ErrorMessage error={error} />

      <div className="flex flex-col gap-2 rounded border border-slate-200 bg-white p-4 text-sm">
        <div className="flex gap-2">
          <input
            className="flex-1 rounded border border-slate-300 px-2 py-1"
            placeholder={t("name")}
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <button
            type="button"
            onClick={create}
            className="rounded bg-slate-900 px-4 py-1 text-white disabled:opacity-50"
            disabled={!name.trim()}
          >
            {t("create")}
          </button>
        </div>

        {created && (
          <div className="rounded border border-amber-300 bg-amber-50 p-3">
            <p className="font-medium">{t("created")}</p>
            <p className="text-xs text-slate-600">{t("createdHint")}</p>
            <div className="mt-2 flex items-center gap-2">
              <code className="flex-1 overflow-x-auto rounded bg-white px-2 py-1">
                {created}
              </code>
              <button
                type="button"
                onClick={copy}
                className="rounded border border-slate-300 px-2 py-1"
              >
                {copied ? t("copied") : t("copy")}
              </button>
            </div>
          </div>
        )}

        {keys.length === 0 ? (
          <p className="text-slate-500">{t("empty")}</p>
        ) : (
          <table className="w-full text-left">
            <thead className="text-xs uppercase text-slate-400">
              <tr>
                <th className="py-1">{t("name")}</th>
                <th className="py-1">{t("prefix")}</th>
                <th className="py-1">{common("status")}</th>
                <th className="py-1">{t("lastUsed")}</th>
                <th className="py-1" />
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr key={key.id} className="border-t border-slate-100">
                  <td className="py-1">{key.name}</td>
                  <td className="py-1 font-mono text-xs">{key.prefix}…</td>
                  <td className="py-1">
                    {key.is_active ? t("active") : t("inactive")}
                  </td>
                  <td className="py-1 text-xs text-slate-500">
                    {key.last_used_at ?? t("never")}
                  </td>
                  <td className="py-1 text-right">
                    <button
                      type="button"
                      onClick={() => toggle(key)}
                      className="rounded border border-slate-300 px-2 py-0.5 text-xs"
                    >
                      {key.is_active ? t("revoke") : t("restore")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
