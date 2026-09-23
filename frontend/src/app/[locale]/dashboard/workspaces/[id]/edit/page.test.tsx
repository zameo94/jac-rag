import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
const refreshTenants = vi.fn().mockResolvedValue(undefined);

const apiMock = vi.hoisted(() => ({
  members: { me: vi.fn() },
  tenants: { update: vi.fn() },
}));

const state = vi.hoisted(() => ({
  id: "1",
  loading: false,
  tenants: [
    {
      id: 1,
      name: "Acme",
      slug: "acme",
      default_locale: "it",
      answer_mode: "strict",
      is_active: true,
    },
  ],
}));

vi.mock("next/navigation", () => ({ useParams: () => ({ id: state.id }) }));

vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => {
    const messages: Record<string, string> = {
      "tenants.editTitle": "Edit workspace",
      "tenants.notFound": "Workspace not found.",
      "tenants.forbidden": "You do not have permission to edit this workspace.",
      "tenants.name": "Name",
      "tenants.slug": "Identifier",
      "tenants.defaultLocale": "Default language",
      "tenants.answerMode": "Answer mode",
      "tenants.strict": "Strict",
      "tenants.assistive": "Assistive",
      "tenants.status": "Status",
      "tenants.active": "Active",
      "tenants.inactive": "Inactive",
      "tenants.statusHint": "hint",
      "tenants.saving": "Saving...",
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

vi.mock("@/features/tenants/TenantProvider", () => ({
  useTenant: () => ({
    tenants: state.tenants,
    loading: state.loading,
    refreshTenants,
  }),
}));

vi.mock("@/lib/api", () => ({ api: apiMock }));

import EditWorkspacePage from "@/app/[locale]/dashboard/workspaces/[id]/edit/page";

beforeEach(() => {
  push.mockClear();
  refreshTenants.mockClear();
  apiMock.members.me.mockReset();
  apiMock.tenants.update.mockReset();
  apiMock.members.me.mockResolvedValue({ role: "OWNER" });
  state.id = "1";
  state.loading = false;
});

describe("EditWorkspacePage", () => {
  it("shows the edit form for an admin", async () => {
    render(<EditWorkspacePage />);

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Edit workspace" })).toBeInTheDocument(),
    );
    expect(screen.getByLabelText("Name")).toHaveValue("Acme");
  });

  it("shows a forbidden message for a member", async () => {
    apiMock.members.me.mockResolvedValue({ role: "MEMBER" });

    render(<EditWorkspacePage />);

    await waitFor(() =>
      expect(
        screen.getByText("You do not have permission to edit this workspace."),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByLabelText("Name")).not.toBeInTheDocument();
  });

  it("shows a not found message for an unknown workspace", async () => {
    state.id = "999";

    render(<EditWorkspacePage />);

    await waitFor(() =>
      expect(screen.getByText("Workspace not found.")).toBeInTheDocument(),
    );
  });
});
