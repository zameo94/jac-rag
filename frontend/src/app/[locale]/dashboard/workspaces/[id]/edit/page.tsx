"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";

import { BackLink } from "@/components/BackLink";
import { useWorkspace } from "@/features/workspaces/WorkspaceProvider";
import { EditWorkspaceForm } from "@/features/workspaces/EditWorkspaceForm";
import { useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import type { MembershipRole } from "@/lib/types";

export default function EditWorkspacePage() {
  const t = useTranslations("workspaces");
  const params = useParams();
  const router = useRouter();
  const { workspaces, loading } = useWorkspace();
  const [role, setRole] = useState<MembershipRole | null>(null);
  const [roleChecked, setRoleChecked] = useState(false);

  const id = Number(params.id);
  const workspace = workspaces.find((item) => item.id === id) ?? null;

  useEffect(() => {
    if (!workspace) return;
    let mounted = true;
    setRoleChecked(false);
    void api.members
      .me(workspace.id)
      .then((membership) => {
        if (mounted) setRole(membership.role);
      })
      .catch(() => {
        if (mounted) setRole(null);
      })
      .finally(() => {
        if (mounted) setRoleChecked(true);
      });
    return () => {
      mounted = false;
    };
  }, [workspace]);

  if (loading || (workspace !== null && !roleChecked)) {
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

  if (role !== "OWNER" && role !== "ADMIN") {
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
