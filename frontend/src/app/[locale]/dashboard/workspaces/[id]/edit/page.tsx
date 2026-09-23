"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";

import { BackLink } from "@/components/BackLink";
import { useTenant } from "@/features/tenants/TenantProvider";
import { EditWorkspaceForm } from "@/features/workspaces/EditWorkspaceForm";
import { useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import type { MembershipRole } from "@/lib/types";

export default function EditWorkspacePage() {
  const t = useTranslations("tenants");
  const params = useParams();
  const router = useRouter();
  const { tenants, loading } = useTenant();
  const [role, setRole] = useState<MembershipRole | null>(null);
  const [roleChecked, setRoleChecked] = useState(false);

  const id = Number(params.id);
  const tenant = tenants.find((item) => item.id === id) ?? null;

  useEffect(() => {
    if (!tenant) return;
    let mounted = true;
    setRoleChecked(false);
    void api.members
      .me(tenant.id)
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
  }, [tenant]);

  if (loading || (tenant !== null && !roleChecked)) {
    return <p className="text-slate-500">...</p>;
  }

  if (!tenant) {
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
          tenant={tenant}
          onDone={() => router.push("/dashboard/workspaces")}
        />
      </div>
    </section>
  );
}
