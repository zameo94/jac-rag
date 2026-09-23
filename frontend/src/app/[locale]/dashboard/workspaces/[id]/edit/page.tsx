"use client";

import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";

import { BackLink } from "@/components/BackLink";
import { EditWorkspaceForm } from "@/features/workspaces/EditWorkspaceForm";
import { useWorkspace } from "@/features/workspaces/WorkspaceProvider";
import { useRouter } from "@/i18n/navigation";

export default function EditWorkspacePage() {
  const t = useTranslations("workspaces");
  const params = useParams();
  const router = useRouter();
  const { workspaces, loading } = useWorkspace();

  const id = Number(params.id);
  const workspace = workspaces.find((item) => item.id === id) ?? null;

  if (loading) {
    return <p className="text-slate-500">...</p>;
  }

  if (!workspace) {
    return (
      <section className="mx-auto max-w-md">
        <BackLink href="/dashboard/workspaces" />
        <p className="mt-4 text-slate-500">{t("notFound")}</p>
      </section>
    );
  }

  if (workspace.role !== "OWNER" && workspace.role !== "ADMIN") {
    return (
      <section className="mx-auto max-w-md">
        <BackLink href="/dashboard/workspaces" />
        <p className="mt-4 text-slate-500">{t("forbidden")}</p>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-md">
      <BackLink href="/dashboard/workspaces" />
      <h1 className="mt-3 text-2xl font-semibold">{t("editTitle")}</h1>
      <div className="mt-4">
        <EditWorkspaceForm
          workspace={workspace}
          onDone={() => router.push("/dashboard/workspaces")}
        />
      </div>
    </section>
  );
}
