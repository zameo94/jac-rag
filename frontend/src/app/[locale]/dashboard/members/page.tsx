"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { ErrorMessage } from "@/components/ErrorMessage";
import { useAuth } from "@/features/auth/AuthProvider";
import { useTenant } from "@/features/tenants/TenantProvider";
import { api } from "@/lib/api";
import type { InvitationCreated, Member, MembershipRole } from "@/lib/types";

const ROLES: MembershipRole[] = ["OWNER", "ADMIN", "MEMBER"];

export default function MembersPage() {
  const t = useTranslations("members");
  const common = useTranslations("common");
  const { user } = useAuth();
  const { activeTenant } = useTenant();
  const [members, setMembers] = useState<Member[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<MembershipRole>("MEMBER");
  const [invitation, setInvitation] = useState<InvitationCreated | null>(null);
  const [copied, setCopied] = useState(false);

  const tenantId = activeTenant?.id ?? null;
  const currentMember = members.find((member) => member.email === user?.email);
  const canManage = currentMember?.role === "OWNER" || currentMember?.role === "ADMIN";

  const load = useCallback(async () => {
    if (!tenantId) return;
    try {
      setMembers(await api.members.list(tenantId));
      setError(null);
    } catch (err) {
      setError(err);
    }
  }, [tenantId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleInvite(event: React.FormEvent) {
    event.preventDefault();
    if (!tenantId) return;
    setError(null);
    try {
      const created = await api.invitations.create(tenantId, email, role);
      setInvitation(created);
      setCopied(false);
      setEmail("");
      await load();
    } catch (err) {
      setError(err);
    }
  }

  async function handleRoleChange(member: Member, nextRole: MembershipRole) {
    if (!tenantId) return;
    try {
      await api.members.updateRole(tenantId, member.user_id, nextRole);
      await load();
    } catch (err) {
      setError(err);
    }
  }

  async function handleRemove(member: Member) {
    if (!tenantId) return;
    if (!window.confirm(common("confirmDelete"))) return;
    try {
      await api.members.remove(tenantId, member.user_id);
      await load();
    } catch (err) {
      setError(err);
    }
  }

  async function copyToken() {
    if (!invitation) return;
    await navigator.clipboard.writeText(invitation.token);
    setCopied(true);
  }

  if (!tenantId) return null;

  return (
    <section className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">{t("title")}</h1>
      <ErrorMessage error={error} />

      {canManage && (
        <form onSubmit={handleInvite} className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm">
            {t("inviteEmail")}
            <input
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="rounded border border-slate-300 px-3 py-2"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            {t("inviteRole")}
            <select
              value={role}
              onChange={(event) => setRole(event.target.value as MembershipRole)}
              className="rounded border border-slate-300 px-3 py-2"
            >
              <option value="MEMBER">{t("roles.MEMBER")}</option>
              <option value="ADMIN">{t("roles.ADMIN")}</option>
            </select>
          </label>
          <button
            type="submit"
            className="rounded bg-slate-900 px-4 py-2 text-sm text-white"
          >
            {t("inviteCta")}
          </button>
        </form>
      )}

      {invitation && (
        <div className="rounded border border-amber-300 bg-amber-50 p-4 text-sm">
          <p className="font-medium">{t("inviteTokenTitle")}</p>
          <p className="text-slate-600">{t("inviteTokenHint")}</p>
          <div className="mt-2 flex items-center gap-2">
            <code className="rounded bg-white px-2 py-1">{invitation.token}</code>
            <button
              type="button"
              onClick={copyToken}
              className="rounded border border-slate-300 px-2 py-1"
            >
              {copied ? t("copied") : t("copy")}
            </button>
          </div>
        </div>
      )}

      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-slate-500">
            <th className="py-2">{common("email")}</th>
            <th className="py-2">{common("role")}</th>
            <th className="py-2" />
          </tr>
        </thead>
        <tbody>
          {members.map((member) => (
            <tr key={member.id} className="border-b border-slate-100">
              <td className="py-2">{member.email}</td>
              <td className="py-2">
                {canManage && member.role !== "OWNER" ? (
                  <select
                    value={member.role}
                    onChange={(event) =>
                      handleRoleChange(member, event.target.value as MembershipRole)
                    }
                    className="rounded border border-slate-300 px-2 py-1"
                  >
                    <option value="MEMBER">{t("roles.MEMBER")}</option>
                    <option value="ADMIN">{t("roles.ADMIN")}</option>
                  </select>
                ) : (
                  <span>{t(`roles.${member.role}`)}</span>
                )}
              </td>
              <td className="py-2 text-right">
                {canManage && member.role !== "OWNER" && member.email !== user?.email && (
                  <button
                    type="button"
                    onClick={() => handleRemove(member)}
                    className="text-sm text-red-600 hover:underline"
                  >
                    {t("remove")}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
