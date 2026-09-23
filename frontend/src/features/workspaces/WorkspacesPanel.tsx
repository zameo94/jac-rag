"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { ErrorMessage } from "@/components/ErrorMessage";
import { PencilIcon, TrashIcon } from "@/components/icons";
import { useWorkspace } from "@/features/workspaces/WorkspaceProvider";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";
import type { Workspace } from "@/lib/types";

export function WorkspacesPanel() {
  const t = useTranslations("workspaces");
  const { workspaces, activeWorkspace, selectWorkspace, refreshWorkspaces } = useWorkspace();
  const [error, setError] = useState<unknown>(null);

  function canManage(workspace: Workspace): boolean {
    return workspace.role === "OWNER" || workspace.role === "ADMIN";
  }

  async function handleDelete(workspace: Workspace) {
    if (!window.confirm(t("deleteConfirm"))) return;
    setError(null);
    try {
      await api.workspaces.remove(workspace.id);
      await refreshWorkspaces();
    } catch (err) {
      setError(err);
    }
  }

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <Link
          href="/dashboard/workspaces/new"
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white hover:bg-slate-800"
        >
          {t("new")}
        </Link>
      </div>

      <ErrorMessage error={error} />

      {workspaces.length === 0 ? (
        <p className="text-slate-500">{t("empty")}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {workspaces.map((workspace) => (
            <li
              key={workspace.id}
              className="flex items-center justify-between rounded border border-slate-200 bg-white p-3 text-sm"
            >
              <span>
                <span className="font-medium">{workspace.name}</span>{" "}
                <span className="text-slate-400">{workspace.slug}</span>
              </span>
              <span className="flex items-center gap-3">
                <span
                  className={`rounded px-2 py-0.5 text-xs ${
                    workspace.is_active
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-slate-100 text-slate-500"
                  }`}
                >
                  {workspace.is_active ? t("active") : t("inactive")}
                </span>
                {workspace.id === activeWorkspace?.id ? (
                  <span className="text-xs text-slate-500">{t("current")}</span>
                ) : (
                  <button
                    type="button"
                    onClick={() => selectWorkspace(workspace.id)}
                    className="text-xs underline"
                  >
                    {t("switch")}
                  </button>
                )}
                {canManage(workspace) && (
                  <Link
                    href={`/dashboard/workspaces/${workspace.id}/edit`}
                    aria-label={t("edit")}
                    className="text-slate-500 hover:text-slate-900"
                  >
                    <PencilIcon className="h-4 w-4" />
                  </Link>
                )}
                {workspace.role === "OWNER" && (
                  <button
                    type="button"
                    aria-label={t("delete")}
                    onClick={() => handleDelete(workspace)}
                    className="text-red-600 hover:text-red-700"
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
