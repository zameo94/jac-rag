import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock("@/features/auth/AuthProvider", () => ({
  useAuth: () => ({ user: { id: 1, email: "user@example.com" } }),
}));

vi.mock("@/features/tenants/TenantProvider", () => ({
  useTenant: () => ({ activeTenant: { id: 1 } }),
}));

const apiMock = vi.hoisted(() => ({
  members: { me: vi.fn() },
  apiKeys: { list: vi.fn(), create: vi.fn(), setActive: vi.fn() },
}));

vi.mock("@/lib/api", () => ({ api: apiMock }));

import { EmbedKeysPanel } from "@/features/embed-keys/EmbedKeysPanel";

beforeEach(() => {
  vi.clearAllMocks();
  apiMock.members.me.mockResolvedValue({ id: 1, user_id: 1, tenant_id: 1, role: "OWNER" });
  apiMock.apiKeys.list.mockResolvedValue([
    {
      id: 1,
      tenant_id: 1,
      name: "Widget",
      prefix: "jrk_abc",
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
      last_used_at: null,
    },
  ]);
});

describe("EmbedKeysPanel", () => {
  it("lists keys and reveals a newly created one once", async () => {
    apiMock.apiKeys.create.mockResolvedValue({ id: 2, key: "jrk_new_secret" });

    render(<EmbedKeysPanel />);

    await waitFor(() => expect(screen.getByText("Widget")).toBeInTheDocument());

    fireEvent.change(screen.getByPlaceholderText("name"), {
      target: { value: "New" },
    });
    fireEvent.click(screen.getByText("create"));

    await waitFor(() =>
      expect(screen.getByText("jrk_new_secret")).toBeInTheDocument(),
    );
    expect(apiMock.apiKeys.create).toHaveBeenCalledWith(1, "New");
  });

  it("is hidden for a member", async () => {
    apiMock.members.me.mockResolvedValue({ id: 1, user_id: 1, tenant_id: 1, role: "MEMBER" });

    const { container } = render(<EmbedKeysPanel />);

    await waitFor(() => expect(apiMock.members.me).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
