import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OptionsMenu } from "@/features/navigation/OptionsMenu";

const logout = vi.fn();
const selectWorkspace = vi.fn();

const state = vi.hoisted(() => ({
  workspaces: [
    { id: 1, name: "Acme", slug: "acme" },
    { id: 2, name: "Beta", slug: "beta" },
  ] as { id: number; name: string; slug: string }[],
  activeWorkspaceId: 1,
}));

vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => {
    const messages: Record<string, string> = {
      "nav.menu": "Menu",
      "nav.documents": "Documents",
      "nav.chat": "Chat",
      "nav.conversations": "Conversations",
      "nav.members": "Members",
      "nav.settings": "Settings",
      "nav.workspaces": "Workspaces",
      "auth.logout": "Log out",
      "workspaces.switch": "Switch workspace",
    };
    return (key: string) => messages[`${namespace}.${key}`] ?? key;
  },
}));

vi.mock("@/i18n/navigation", () => ({
  usePathname: () => "/dashboard",
  Link: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/features/auth/AuthProvider", () => ({
  useAuth: () => ({ logout }),
}));

vi.mock("@/features/workspaces/WorkspaceProvider", () => ({
  useWorkspace: () => ({
    workspaces: state.workspaces,
    activeWorkspace: state.workspaces.find((workspace) => workspace.id === state.activeWorkspaceId),
    selectWorkspace,
  }),
}));

beforeEach(() => {
  logout.mockClear();
  selectWorkspace.mockClear();
  state.activeWorkspaceId = 1;
  state.workspaces = [
    { id: 1, name: "Acme", slug: "acme" },
    { id: 2, name: "Beta", slug: "beta" },
  ];
});

describe("OptionsMenu", () => {
  it("renders a closed menu button", () => {
    render(<OptionsMenu />);

    const trigger = screen.getByRole("button", { name: "Menu" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("shows navigation links when opened", async () => {
    const user = userEvent.setup();
    render(<OptionsMenu />);

    await user.click(screen.getByRole("button", { name: "Menu" }));

    expect(screen.getByRole("menuitem", { name: "Documents" })).toHaveAttribute(
      "href",
      "/dashboard/documents",
    );
    expect(screen.getByRole("menuitem", { name: "Chat" })).toHaveAttribute(
      "href",
      "/dashboard/chat",
    );
    expect(screen.getByRole("menuitem", { name: "Workspaces" })).toHaveAttribute(
      "href",
      "/dashboard/workspaces",
    );

    for (const label of ["Documents", "Chat", "Workspaces"]) {
      expect(
        screen.getByRole("menuitem", { name: label }).querySelector("svg"),
      ).not.toBeNull();
    }
  });

  it("hides the workspace links for a guest", async () => {
    state.workspaces = [];
    const user = userEvent.setup();
    render(<OptionsMenu />);

    await user.click(screen.getByRole("button", { name: "Menu" }));

    expect(screen.queryByRole("menuitem", { name: "Documents" })).not.toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Log out" })).toBeInTheDocument();
  });

  it("lists workspaces and marks the active one", async () => {
    const user = userEvent.setup();
    render(<OptionsMenu />);

    await user.click(screen.getByRole("button", { name: "Menu" }));

    const acme = screen.getByRole("menuitemradio", { name: "Acme" });
    const beta = screen.getByRole("menuitemradio", { name: "Beta" });
    expect(acme).toHaveAttribute("aria-checked", "true");
    expect(beta).toHaveAttribute("aria-checked", "false");
  });

  it("switches workspace and closes the menu", async () => {
    const user = userEvent.setup();
    render(<OptionsMenu />);

    await user.click(screen.getByRole("button", { name: "Menu" }));
    await user.click(screen.getByRole("menuitemradio", { name: "Beta" }));

    expect(selectWorkspace).toHaveBeenCalledWith(2);
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("logs out and closes the menu", async () => {
    const user = userEvent.setup();
    render(<OptionsMenu />);

    await user.click(screen.getByRole("button", { name: "Menu" }));
    await user.click(screen.getByRole("menuitem", { name: "Log out" }));

    expect(logout).toHaveBeenCalled();
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("closes on Escape", async () => {
    const user = userEvent.setup();
    render(<OptionsMenu />);

    await user.click(screen.getByRole("button", { name: "Menu" }));
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });
});
