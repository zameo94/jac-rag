import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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
  vi.stubEnv(
    "NEXT_PUBLIC_WIDGET_SCRIPT_URL",
    "https://cdn.example.com/embed-rag-chatbot.js",
  );
  vi.stubEnv("NEXT_PUBLIC_WIDGET_API_URL", "https://api.example.com");
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

afterEach(() => {
  vi.unstubAllEnvs();
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

  it("shows the embed snippet with a placeholder before a key exists", async () => {
    render(<EmbedKeysPanel />);

    await waitFor(() => expect(screen.getByText("Widget")).toBeInTheDocument());

    const snippet = screen.getByText(/data-embed-key="YOUR_EMBED_KEY"/);
    expect(snippet).toBeInTheDocument();
    expect(snippet).toHaveTextContent(
      'src="https://cdn.example.com/embed-rag-chatbot.js"',
    );
    expect(snippet).toHaveTextContent('data-api-url="https://api.example.com"');
  });

  it("puts the created key into the embed snippet", async () => {
    apiMock.apiKeys.create.mockResolvedValue({ id: 2, key: "jrk_new_secret" });

    render(<EmbedKeysPanel />);

    await waitFor(() => expect(screen.getByText("Widget")).toBeInTheDocument());

    fireEvent.change(screen.getByPlaceholderText("name"), {
      target: { value: "New" },
    });
    fireEvent.click(screen.getByText("create"));

    await waitFor(() =>
      expect(
        screen.getByText(/data-embed-key="jrk_new_secret"/),
      ).toBeInTheDocument(),
    );
  });

  it("copies the snippet to the clipboard", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });

    render(<EmbedKeysPanel />);

    await waitFor(() => expect(screen.getByText("Widget")).toBeInTheDocument());
    fireEvent.click(screen.getByText("copy"));

    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    expect(writeText.mock.calls[0][0]).toContain("data-embed-key=");
    expect(screen.getByText("copied")).toBeInTheDocument();
  });
});
