import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RequireAuth } from "@/features/auth/RequireAuth";

const replace = vi.fn();

const state = vi.hoisted(() => ({
  user: null as { id: number; email: string } | null,
  loading: false,
}));

vi.mock("next-intl", () => ({}));

vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ replace }),
}));

vi.mock("@/features/auth/AuthProvider", () => ({
  useAuth: () => ({ user: state.user, loading: state.loading }),
}));

beforeEach(() => {
  replace.mockClear();
  state.user = null;
  state.loading = false;
});

describe("RequireAuth", () => {
  it("shows a placeholder while loading", () => {
    state.loading = true;

    render(
      <RequireAuth>
        <p>secret</p>
      </RequireAuth>,
    );

    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });

  it("redirects guests to the login page", async () => {
    render(
      <RequireAuth>
        <p>secret</p>
      </RequireAuth>,
    );

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });

  it("renders children for authenticated users", () => {
    state.user = { id: 1, email: "user@example.com" };

    render(
      <RequireAuth>
        <p>secret</p>
      </RequireAuth>,
    );

    expect(screen.getByText("secret")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
