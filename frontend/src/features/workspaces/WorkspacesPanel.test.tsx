import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const selectTenant = vi.fn();
const refreshTenants = vi.fn().mockResolvedValue(undefined);

const apiMock = vi.hoisted(() => ({
  members: { me: vi.fn() },
  tenants: { remove: vi.fn() },
}));

const state = vi.hoisted(() => ({
  tenants: [
    {
      id: 1,
      name: "Acme",
      slug: "acme",
      default_locale: "it",
      answer_mode: "strict",
      is_active: true,
    },
    {
      id: 2,
      name: "Beta",
      slug: "beta",
      default_locale: "it",
      answer_mode: "strict",
      is_active: true,
    },
  ],
  activeTenantId: 1,
}));

vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => {
    const messages: Record<string, string> = {
      "tenants.title": "Your workspaces",
      "tenants.new": "New workspace",
      "tenants.edit": "Edit workspace",
      "tenants.delete": "Delete workspace",
      "tenants.deleteConfirm": "Delete this workspace? Everything will be lost.",
      "tenants.switch": "Switch workspace",
      "tenants.active": "Active",
      "tenants.inactive": "Inactive",
      "tenants.current": "Current",
      "tenants.empty": "No workspaces.",
      "errors.generic": "Generic error",
    };
    return Object.assign((key: string) => messages[`${namespace}.${key}`] ?? key, {
      has: (key: string) => `${namespace}.${key}` in messages,
    });
  },
}));

vi.mock("@/i18n/navigation", () => ({
  Link: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/features/tenants/TenantProvider", () => ({
  useTenant: () => ({
    tenants: state.tenants,
    activeTenant: state.tenants.find((tenant) => tenant.id === state.activeTenantId),
    selectTenant,
    refreshTenants,
  }),
}));

vi.mock("@/lib/api", () => ({ api: apiMock }));

import { WorkspacesPanel } from "@/features/workspaces/WorkspacesPanel";

beforeEach(() => {
  selectTenant.mockClear();
  refreshTenants.mockClear();
  apiMock.members.me.mockReset();
  apiMock.tenants.remove.mockReset();
  apiMock.members.me.mockImplementation((id: number) =>
    Promise.resolve({ role: id === 1 ? "OWNER" : "MEMBER" }),
  );
  apiMock.tenants.remove.mockResolvedValue(undefined);
  state.activeTenantId = 1;
  state.tenants = [
    {
      id: 1,
      name: "Acme",
      slug: "acme",
      default_locale: "it",
      answer_mode: "strict",
      is_active: true,
    },
    {
      id: 2,
      name: "Beta",
      slug: "beta",
      default_locale: "it",
      answer_mode: "strict",
      is_active: true,
    },
  ];
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("WorkspacesPanel", () => {
  it("lists the workspaces and marks the current one", () => {
    render(<WorkspacesPanel />);

    expect(screen.getByText("Acme")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
    expect(screen.getByText("Current")).toBeInTheDocument();
  });

  it("links to the new workspace form", () => {
    render(<WorkspacesPanel />);

    expect(screen.getByRole("link", { name: "New workspace" })).toHaveAttribute(
      "href",
      "/dashboard/workspaces/new",
    );
  });

  it("switches to another workspace", async () => {
    const user = userEvent.setup();
    render(<WorkspacesPanel />);

    await user.click(screen.getByRole("button", { name: "Switch workspace" }));

    expect(selectTenant).toHaveBeenCalledWith(2);
  });

  it("shows an empty state for a guest", () => {
    state.tenants = [];

    render(<WorkspacesPanel />);

    expect(screen.getByText("No workspaces.")).toBeInTheDocument();
  });

  it("shows the edit link only for workspaces the user can manage", async () => {
    render(<WorkspacesPanel />);

    await waitFor(() =>
      expect(screen.getAllByRole("link", { name: "Edit workspace" })).toHaveLength(1),
    );
    expect(screen.getByRole("link", { name: "Edit workspace" })).toHaveAttribute(
      "href",
      "/dashboard/workspaces/1/edit",
    );
  });

  it("shows an inactive badge for a deactivated workspace", () => {
    state.tenants[1].is_active = false;

    render(<WorkspacesPanel />);

    expect(screen.getByText("Inactive")).toBeInTheDocument();
  });

  it("shows the delete action only for owned workspaces", async () => {
    render(<WorkspacesPanel />);

    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: "Delete workspace" })).toHaveLength(1),
    );
  });

  it("deletes the workspace after confirmation", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    render(<WorkspacesPanel />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Delete workspace" })).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: "Delete workspace" }));

    await waitFor(() => expect(apiMock.tenants.remove).toHaveBeenCalledWith(1));
    expect(refreshTenants).toHaveBeenCalled();
  });

  it("does not delete when the confirmation is dismissed", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const user = userEvent.setup();
    render(<WorkspacesPanel />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Delete workspace" })).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: "Delete workspace" }));

    expect(apiMock.tenants.remove).not.toHaveBeenCalled();
  });
});
