"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { ErrorMessage } from "@/components/ErrorMessage";
import { useTenant } from "@/features/tenants/TenantProvider";
import { api } from "@/lib/api";
import type { Conversation, ConversationDetail, MembershipRole } from "@/lib/types";

export function ConversationsPanel() {
  const t = useTranslations("conversations");
  const common = useTranslations("common");
  const { activeTenant } = useTenant();
  const [items, setItems] = useState<Conversation[]>([]);
  const [role, setRole] = useState<MembershipRole | null>(null);
  const [selected, setSelected] = useState<ConversationDetail | null>(null);
  const [error, setError] = useState<unknown>(null);

  const tenantId = activeTenant?.id ?? null;
  const isManager = role === "OWNER" || role === "ADMIN";

  const load = useCallback(async () => {
    if (!tenantId) return;
    try {
      const membership = await api.members.me(tenantId);
      setRole(membership.role);
      if (membership.role === "OWNER" || membership.role === "ADMIN") {
        setItems(await api.conversations.list(tenantId));
      }
      setError(null);
    } catch (err) {
      setError(err);
    }
  }, [tenantId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!tenantId || !isManager) return null;

  async function open(conversation: Conversation) {
    if (!tenantId) return;
    try {
      setSelected(await api.conversations.get(tenantId, conversation.id));
    } catch (err) {
      setError(err);
    }
  }

  async function remove(conversation: Conversation) {
    if (!tenantId) return;
    try {
      await api.conversations.remove(tenantId, conversation.id);
      if (selected?.id === conversation.id) setSelected(null);
      await load();
    } catch (err) {
      setError(err);
    }
  }

  return (
    <section className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">{t("title")}</h1>
      <ErrorMessage error={error} />

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded border border-slate-200 bg-white p-4 text-sm">
          {items.length === 0 ? (
            <p className="text-slate-500">{t("empty")}</p>
          ) : (
            <ul className="flex flex-col divide-y divide-slate-100">
              {items.map((conversation) => (
                <li key={conversation.id} className="flex items-center gap-2 py-2">
                  <button
                    type="button"
                    onClick={() => open(conversation)}
                    className="flex-1 text-left hover:underline"
                  >
                    <span className="font-medium">{conversation.title ?? "—"}</span>
                    <span className="block text-xs text-slate-500">
                      {conversation.end_user_id ? t("visitor") : t("user")}
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => remove(conversation)}
                    className="rounded border border-slate-300 px-2 py-0.5 text-xs text-red-600"
                  >
                    {common("delete")}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded border border-slate-200 bg-white p-4 text-sm">
          {selected === null ? (
            <p className="text-slate-500">{t("select")}</p>
          ) : (
            <div className="flex flex-col gap-2">
              {selected.messages.map((message) => (
                <div
                  key={message.id}
                  className={`rounded p-2 ${
                    message.role === "user" ? "bg-slate-100" : "bg-emerald-50"
                  }`}
                >
                  <p className="text-xs uppercase text-slate-400">{message.role}</p>
                  <p className="whitespace-pre-wrap">{message.content}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
