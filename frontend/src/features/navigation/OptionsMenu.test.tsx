import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OptionsMenu } from "@/features/navigation/OptionsMenu";

const logout = vi.fn();
const selectTenant = vi.fn();

const state = vi.hoisted(() => ({
  user: { id: 1, email: "user@example.com" } as { id: number; email: string } | null,
  tenants: [
    { id: 1, name: "Acme", slug: "acme" },
    { id: 2, name: "Beta", slug: "beta" },
  ],
  activeTenantId: 1,
}));

vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => {
    const messages: Record<string, string> = {
      "nav.menu": "Menu",
      "nav.documents": "Documents",
      "nav.members": "Members",
      "nav.settings": "Settings",
      "auth.logout": "Log out",
      "auth.goLogin": "Sign in",
      "auth.goRegister": "Sign up",
      "tenants.switch": "Switch workspace",
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
  useAuth: () => ({ user: state.user, logout }),
}));

vi.mock("@/features/tenants/TenantProvider", () => ({
  useTenant: () => ({
    tenants: state.tenants,
    activeTenant: state.tenants.find((tenant) => tenant.id === state.activeTenantId),
    selectTenant,
  }),
}));

beforeEach(() => {
  logout.mockClear();
  selectTenant.mockClear();
  state.user = { id: 1, email: "user@example.com" };
  state.activeTenantId = 1;
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
      "/dashboard",
    );
    expect(screen.getByRole("menuitem", { name: "Members" })).toHaveAttribute(
      "href",
      "/dashboard/members",
    );
    expect(screen.getByRole("menuitem", { name: "Settings" })).toHaveAttribute(
      "href",
      "/dashboard/settings",
    );
  });

  it("lists tenants and marks the active one", async () => {
    const user = userEvent.setup();
    render(<OptionsMenu />);

    await user.click(screen.getByRole("button", { name: "Menu" }));

    const acme = screen.getByRole("menuitemradio", { name: "Acme" });
    const beta = screen.getByRole("menuitemradio", { name: "Beta" });
    expect(acme).toHaveAttribute("aria-checked", "true");
    expect(beta).toHaveAttribute("aria-checked", "false");
  });

  it("switches tenant and closes the menu", async () => {
    const user = userEvent.setup();
    render(<OptionsMenu />);

    await user.click(screen.getByRole("button", { name: "Menu" }));
    await user.click(screen.getByRole("menuitemradio", { name: "Beta" }));

    expect(selectTenant).toHaveBeenCalledWith(2);
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

  it("shows only auth links for guests", async () => {
    state.user = null;
    const user = userEvent.setup();
    render(<OptionsMenu />);

    await user.click(screen.getByRole("button", { name: "Menu" }));

    expect(screen.getByRole("menuitem", { name: "Sign in" })).toHaveAttribute(
      "href",
      "/login",
    );
    expect(screen.getByRole("menuitem", { name: "Sign up" })).toHaveAttribute(
      "href",
      "/register",
    );
    expect(screen.queryByRole("menuitem", { name: "Documents" })).not.toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Log out" })).not.toBeInTheDocument();
  });

  it("closes on Escape", async () => {
    const user = userEvent.setup();
    render(<OptionsMenu />);

    await user.click(screen.getByRole("button", { name: "Menu" }));
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });
});
