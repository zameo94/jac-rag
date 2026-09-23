import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
const refreshWorkspaces = vi.fn().mockResolvedValue(undefined);

const apiMock = vi.hoisted(() => ({
  workspaces: { update: vi.fn() },
}));

const state = vi.hoisted(() => ({
  id: "1",
  loading: false,
  workspaces: [
    {
      id: 1,
      name: "Acme",
      slug: "acme",
      default_locale: "it",
      answer_mode: "strict" as const,
      is_active: true,
      role: "OWNER" as "OWNER" | "ADMIN" | "MEMBER",
    },
  ],
}));

vi.mock("next/navigation", () => ({ useParams: () => ({ id: state.id }) }));

vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => {
    const messages: Record<string, string> = {
      "workspaces.editTitle": "Edit workspace",
      "workspaces.notFound": "Workspace not found.",
      "workspaces.forbidden": "You do not have permission to edit this workspace.",
      "workspaces.name": "Name",
      "workspaces.slug": "Identifier",
      "workspaces.defaultLocale": "Default language",
      "workspaces.answerMode": "Answer mode",
      "workspaces.strict": "Strict",
      "workspaces.assistive": "Assistive",
      "workspaces.status": "Status",
      "workspaces.active": "Active",
      "workspaces.inactive": "Inactive",
      "workspaces.statusHint": "hint",
      "workspaces.saving": "Saving...",
      "common.save": "Save",
      "common.cancel": "Cancel",
      "common.back": "Back",
      "errors.generic": "Generic error",
    };
    return Object.assign((key: string) => messages[`${namespace}.${key}`] ?? key, {
      has: () => false,
    });
  },
}));

vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ push }),
  Link: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/features/workspaces/WorkspaceProvider", () => ({
  useWorkspace: () => ({
    workspaces: state.workspaces,
    loading: state.loading,
    refreshWorkspaces,
  }),
}));

vi.mock("@/lib/api", () => ({ api: apiMock }));

import EditWorkspacePage from "@/app/[locale]/dashboard/workspaces/[id]/edit/page";

beforeEach(() => {
  push.mockClear();
  refreshWorkspaces.mockClear();
  apiMock.workspaces.update.mockReset();
  state.id = "1";
  state.loading = false;
  state.workspaces[0].role = "OWNER";
});

describe("EditWorkspacePage", () => {
  it("shows the edit form for an owner", () => {
    render(<EditWorkspacePage />);

    expect(
      screen.getByRole("heading", { name: "Edit workspace" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toHaveValue("Acme");
  });

  it("shows the edit form for an admin", () => {
    state.workspaces[0].role = "ADMIN";

    render(<EditWorkspacePage />);

    expect(screen.getByLabelText("Name")).toHaveValue("Acme");
  });

  it("shows a forbidden message for a member", () => {
    state.workspaces[0].role = "MEMBER";

    render(<EditWorkspacePage />);

    expect(
      screen.getByText("You do not have permission to edit this workspace."),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Name")).not.toBeInTheDocument();
  });

  it("shows a not found message for an unknown workspace", () => {
    state.id = "999";

    render(<EditWorkspacePage />);

    expect(screen.getByText("Workspace not found.")).toBeInTheDocument();
  });
});
