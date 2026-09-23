import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceGuard } from "@/features/workspaces/WorkspaceGuard";

const replace = vi.fn();

const state = vi.hoisted(() => ({
  workspaces: [] as { id: number }[],
  loading: false,
  pathname: "/dashboard",
}));

vi.mock("@/i18n/navigation", () => ({
  usePathname: () => state.pathname,
  useRouter: () => ({ replace }),
}));

vi.mock("@/features/workspaces/WorkspaceProvider", () => ({
  useWorkspace: () => ({ workspaces: state.workspaces, loading: state.loading }),
}));

beforeEach(() => {
  replace.mockClear();
  state.workspaces = [];
  state.loading = false;
  state.pathname = "/dashboard";
});

describe("WorkspaceGuard", () => {
  it("redirects a guest away from a workspace-only page", async () => {
    state.pathname = "/dashboard/documents";

    render(
      <WorkspaceGuard>
        <p>child</p>
      </WorkspaceGuard>,
    );

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
  });

  it("lets a guest stay on the dashboard gate", async () => {
    state.pathname = "/dashboard";

    render(
      <WorkspaceGuard>
        <p>child</p>
      </WorkspaceGuard>,
    );

    await waitFor(() => expect(replace).not.toHaveBeenCalled());
  });

  it("lets a guest stay on the new workspace form", async () => {
    state.pathname = "/dashboard/workspaces/new";

    render(
      <WorkspaceGuard>
        <p>child</p>
      </WorkspaceGuard>,
    );

    await waitFor(() => expect(replace).not.toHaveBeenCalled());
  });

  it("does not redirect a user with at least one workspace", async () => {
    state.workspaces = [{ id: 1 }];
    state.pathname = "/dashboard/settings";

    render(
      <WorkspaceGuard>
        <p>child</p>
      </WorkspaceGuard>,
    );

    await waitFor(() => expect(replace).not.toHaveBeenCalled());
  });

  it("waits while workspaces are still loading", async () => {
    state.loading = true;
    state.pathname = "/dashboard/documents";

    render(
      <WorkspaceGuard>
        <p>child</p>
      </WorkspaceGuard>,
    );

    await waitFor(() => expect(replace).not.toHaveBeenCalled());
  });
});
