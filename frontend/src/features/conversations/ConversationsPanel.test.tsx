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
  members: { list: vi.fn() },
  conversations: { list: vi.fn(), get: vi.fn(), remove: vi.fn() },
}));

vi.mock("@/lib/api", () => ({ api: apiMock }));

import { ConversationsPanel } from "@/features/conversations/ConversationsPanel";

beforeEach(() => {
  vi.clearAllMocks();
  apiMock.members.list.mockResolvedValue([{ user_id: 1, role: "ADMIN" }]);
  apiMock.conversations.list.mockResolvedValue([
    {
      id: 7,
      tenant_id: 1,
      user_id: null,
      end_user_id: "visitor-1",
      title: "Come si fa?",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
  ]);
  apiMock.conversations.get.mockResolvedValue({
    id: 7,
    tenant_id: 1,
    user_id: null,
    end_user_id: "visitor-1",
    title: "Come si fa?",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    messages: [
      {
        id: 1,
        conversation_id: 7,
        role: "user",
        content: "Domanda",
        provider: null,
        model: null,
        grounded: null,
        error_code: null,
        sources: null,
        created_at: "2026-01-01T00:00:00Z",
      },
    ],
  });
});

describe("ConversationsPanel", () => {
  it("lists conversations and opens the detail", async () => {
    render(<ConversationsPanel />);

    await waitFor(() => expect(screen.getByText("Come si fa?")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Come si fa?"));

    await waitFor(() => expect(screen.getByText("Domanda")).toBeInTheDocument());
  });

  it("deletes a conversation", async () => {
    render(<ConversationsPanel />);

    await waitFor(() => expect(screen.getByText("Come si fa?")).toBeInTheDocument());

    fireEvent.click(screen.getByText("delete"));

    await waitFor(() =>
      expect(apiMock.conversations.remove).toHaveBeenCalledWith(1, 7),
    );
  });
});
