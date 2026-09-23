import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({ locale: "en" }));
const apiMock = vi.hoisted(() => ({
  auth: { me: vi.fn(), updateLocale: vi.fn(), logout: vi.fn() },
}));

vi.mock("next-intl", () => ({ useLocale: () => state.locale }));

vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("@/lib/api", () => ({ api: apiMock }));

vi.mock("@/lib/session-idle", () => ({
  SESSION_IDLE_TIMEOUT_MS: 0,
  useSessionIdle: vi.fn(),
}));

vi.mock("@/lib/active-tenant-store", () => ({
  activeTenantStore: { clear: vi.fn() },
}));

import { AuthProvider, useAuth } from "@/features/auth/AuthProvider";

function Probe() {
  const { user } = useAuth();
  return <span data-testid="locale">{user?.locale ?? "none"}</span>;
}

beforeEach(() => {
  state.locale = "en";
  apiMock.auth.me.mockReset();
  apiMock.auth.updateLocale.mockReset();
  apiMock.auth.me.mockResolvedValue({ id: 1, locale: "it" });
  apiMock.auth.updateLocale.mockResolvedValue({ id: 1, locale: "en" });
});

describe("AuthProvider locale sync", () => {
  it("persists the UI locale when it differs from the stored one", async () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(apiMock.auth.updateLocale).toHaveBeenCalledWith("en"));
    await waitFor(() =>
      expect(screen.getByTestId("locale")).toHaveTextContent("en"),
    );
  });

  it("does not persist when the locales already match", async () => {
    state.locale = "it";

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(apiMock.auth.me).toHaveBeenCalled());
    expect(apiMock.auth.updateLocale).not.toHaveBeenCalled();
  });
});
