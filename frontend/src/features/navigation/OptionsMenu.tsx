"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import {
  ChatIcon,
  ConversationsIcon,
  DocumentsIcon,
  MembersIcon,
  MenuIcon,
  SettingsIcon,
  WorkspacesIcon,
} from "@/components/icons";
import { useAuth } from "@/features/auth/AuthProvider";
import { useWorkspace } from "@/features/workspaces/WorkspaceProvider";
import { Link, usePathname } from "@/i18n/navigation";

export function OptionsMenu() {
  const t = useTranslations("nav");
  const auth = useTranslations("auth");
  const workspacesLabels = useTranslations("workspaces");
  const { logout } = useAuth();
  const { workspaces, activeWorkspace, selectWorkspace } = useWorkspace();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    function handlePointerDown(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  const links = [
    { href: "/dashboard/documents", label: t("documents"), Icon: DocumentsIcon },
    { href: "/dashboard/chat", label: t("chat"), Icon: ChatIcon },
    {
      href: "/dashboard/conversations",
      label: t("conversations"),
      Icon: ConversationsIcon,
    },
    { href: "/dashboard/members", label: t("members"), Icon: MembersIcon },
    { href: "/dashboard/settings", label: t("settings"), Icon: SettingsIcon },
    { href: "/dashboard/workspaces", label: t("workspaces"), Icon: WorkspacesIcon },
  ];

  function close() {
    setOpen(false);
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t("menu")}
        onClick={() => setOpen((value) => !value)}
        className="flex items-center gap-2 rounded border border-slate-300 bg-white px-2 py-1 text-sm"
      >
        <MenuIcon className="h-4 w-4" />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 w-56 overflow-hidden rounded border border-slate-200 bg-white py-1 shadow-lg"
        >
          {workspaces.length > 0 &&
            links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                role="menuitem"
                aria-current={pathname === link.href}
                onClick={close}
                className={`flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-slate-50 ${
                  pathname === link.href ? "font-medium" : ""
                }`}
              >
                <link.Icon className="h-4 w-4 text-slate-500" />
                {link.label}
              </Link>
            ))}

          {workspaces.length > 0 && (
            <div className="mt-1 border-t border-slate-100 pt-1">
              <p className="px-3 py-1 text-xs uppercase tracking-wide text-slate-400">
                {workspacesLabels("switch")}
              </p>
              {workspaces.map((workspace) => (
                <button
                  key={workspace.id}
                  type="button"
                  role="menuitemradio"
                  aria-checked={workspace.id === activeWorkspace?.id}
                  onClick={() => {
                    selectWorkspace(workspace.id);
                    close();
                  }}
                  className={`flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-slate-50 ${
                    workspace.id === activeWorkspace?.id ? "font-medium" : ""
                  }`}
                >
                  <span
                    aria-hidden="true"
                    className={`h-1.5 w-1.5 rounded-full ${
                      workspace.id === activeWorkspace?.id ? "bg-slate-900" : "bg-transparent"
                    }`}
                  />
                  {workspace.name}
                </button>
              ))}
            </div>
          )}

          <div className="mt-1 border-t border-slate-100 pt-1">
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                close();
                logout();
              }}
              className="block w-full px-3 py-1.5 text-left text-sm text-red-600 hover:bg-slate-50"
            >
              {auth("logout")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
