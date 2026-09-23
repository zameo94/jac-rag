"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { BackLink } from "@/components/BackLink";
import { useWorkspace } from "@/features/workspaces/WorkspaceProvider";
import { CreateWorkspaceForm } from "@/features/workspaces/CreateWorkspaceForm";
import { JoinWorkspaceForm } from "@/features/workspaces/JoinWorkspaceForm";

export default function NewWorkspacePage() {
  const t = useTranslations("workspaces");
  const { workspaces } = useWorkspace();
  const [tab, setTab] = useState<"create" | "join">("create");

  const backHref = workspaces.length > 0 ? "/dashboard/workspaces" : "/dashboard";

  return (
    <section className="mx-auto max-w-md">
      <BackLink href={backHref} />
      <h1 className="mt-3 text-2xl font-semibold">{t("new")}</h1>
      <p className="mt-2 text-sm text-slate-600">{t("newHint")}</p>

      <div className="mt-6 flex gap-2">
        <button
          type="button"
          onClick={() => setTab("create")}
          className={`rounded px-3 py-1 text-sm ${
            tab === "create" ? "bg-slate-900 text-white" : "bg-slate-200"
          }`}
        >
          {t("createCta")}
        </button>
        <button
          type="button"
          onClick={() => setTab("join")}
          className={`rounded px-3 py-1 text-sm ${
            tab === "join" ? "bg-slate-900 text-white" : "bg-slate-200"
          }`}
        >
          {t("joinTitle")}
        </button>
      </div>

      {tab === "create" ? <CreateWorkspaceForm /> : <JoinWorkspaceForm />}
    </section>
  );
}
