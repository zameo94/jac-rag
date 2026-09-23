import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceGuard } from "@/features/workspaces/WorkspaceGuard";

const replace = vi.fn();

const state = vi.hoisted(() => ({
  tenants: [] as { id: number }[],
  loading: false,
  pathname: "/dashboard",
}));

vi.mock("@/i18n/navigation", () => ({
  usePathname: () => state.pathname,
  useRouter: () => ({ replace }),
}));

vi.mock("@/features/tenants/TenantProvider", () => ({
  useTenant: () => ({ tenants: state.tenants, loading: state.loading }),
}));

beforeEach(() => {
  replace.mockClear();
  state.tenants = [];
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
    state.tenants = [{ id: 1 }];
    state.pathname = "/dashboard/settings";

    render(
      <WorkspaceGuard>
        <p>child</p>
      </WorkspaceGuard>,
    );

    await waitFor(() => expect(replace).not.toHaveBeenCalled());
  });

  it("waits while tenants are still loading", async () => {
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
