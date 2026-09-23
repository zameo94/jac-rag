import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const selectWorkspace = vi.fn();
const refreshWorkspaces = vi.fn().mockResolvedValue(undefined);

const apiMock = vi.hoisted(() => ({
  workspaces: { remove: vi.fn() },
}));

const state = vi.hoisted(() => ({
  workspaces: [] as {
    id: number;
    name: string;
    slug: string;
    default_locale: string;
    answer_mode: "strict";
    is_active: boolean;
    role: "OWNER" | "ADMIN" | "MEMBER";
  }[],
  activeWorkspaceId: 1,
}));

function workspace(
  id: number,
  name: string,
  role: "OWNER" | "ADMIN" | "MEMBER",
): (typeof state.workspaces)[number] {
  return {
    id,
    name,
    slug: name.toLowerCase(),
    default_locale: "it",
    answer_mode: "strict",
    is_active: true,
    role,
  };
}

vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => {
    const messages: Record<string, string> = {
      "workspaces.title": "Your workspaces",
      "workspaces.new": "New workspace",
      "workspaces.edit": "Edit workspace",
      "workspaces.delete": "Delete workspace",
      "workspaces.deleteConfirm": "Delete this workspace? Everything will be lost.",
      "workspaces.switch": "Switch workspace",
      "workspaces.active": "Active",
      "workspaces.inactive": "Inactive",
      "workspaces.current": "Current",
      "workspaces.empty": "No workspaces.",
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

vi.mock("@/features/workspaces/WorkspaceProvider", () => ({
  useWorkspace: () => ({
    workspaces: state.workspaces,
    activeWorkspace: state.workspaces.find(
      (entry) => entry.id === state.activeWorkspaceId,
    ),
    selectWorkspace,
    refreshWorkspaces,
  }),
}));

vi.mock("@/lib/api", () => ({ api: apiMock }));

import { WorkspacesPanel } from "@/features/workspaces/WorkspacesPanel";

beforeEach(() => {
  selectWorkspace.mockClear();
  refreshWorkspaces.mockClear();
  apiMock.workspaces.remove.mockReset();
  apiMock.workspaces.remove.mockResolvedValue(undefined);
  state.activeWorkspaceId = 1;
  state.workspaces = [workspace(1, "Acme", "OWNER"), workspace(2, "Beta", "ADMIN")];
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

    expect(selectWorkspace).toHaveBeenCalledWith(2);
  });

  it("shows an empty state for a guest", () => {
    state.workspaces = [];

    render(<WorkspacesPanel />);

    expect(screen.getByText("No workspaces.")).toBeInTheDocument();
  });

  it("shows the edit link for owner and admin only", () => {
    render(<WorkspacesPanel />);

    expect(screen.getAllByRole("link", { name: "Edit workspace" })).toHaveLength(2);
  });

  it("hides the edit link for a member", () => {
    state.workspaces = [workspace(1, "Acme", "OWNER"), workspace(2, "Beta", "MEMBER")];

    render(<WorkspacesPanel />);

    expect(screen.getAllByRole("link", { name: "Edit workspace" })).toHaveLength(1);
  });

  it("shows the delete action for the owner only", () => {
    render(<WorkspacesPanel />);

    expect(screen.getAllByRole("button", { name: "Delete workspace" })).toHaveLength(1);
  });

  it("shows an inactive badge for a deactivated workspace", () => {
    state.workspaces[1].is_active = false;

    render(<WorkspacesPanel />);

    expect(screen.getByText("Inactive")).toBeInTheDocument();
  });

  it("deletes the workspace after confirmation", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    render(<WorkspacesPanel />);

    await user.click(screen.getByRole("button", { name: "Delete workspace" }));

    expect(apiMock.workspaces.remove).toHaveBeenCalledWith(1);
    expect(refreshWorkspaces).toHaveBeenCalled();
  });

  it("does not delete when the confirmation is dismissed", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const user = userEvent.setup();
    render(<WorkspacesPanel />);

    await user.click(screen.getByRole("button", { name: "Delete workspace" }));

    expect(apiMock.workspaces.remove).not.toHaveBeenCalled();
  });
});
