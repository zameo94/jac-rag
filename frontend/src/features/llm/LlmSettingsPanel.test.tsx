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
  llm: {
    config: vi.fn(),
    settings: vi.fn(),
    updateSettings: vi.fn(),
    selectProvider: vi.fn(),
  },
  members: { list: vi.fn() },
}));

vi.mock("@/lib/api", () => ({ api: apiMock }));

import { LlmSettingsPanel } from "@/features/llm/LlmSettingsPanel";

beforeEach(() => {
  vi.clearAllMocks();
  apiMock.llm.config.mockResolvedValue({
    providers: [
      { id: "ollama", enabled: true, models: ["llama3.2"] },
      { id: "external_api", enabled: true, models: ["gpt-x"] },
    ],
    allowed_providers: ["ollama"],
    selected_provider: "ollama",
    default_provider: "ollama",
  });
  apiMock.members.list.mockResolvedValue([{ user_id: 1, role: "MEMBER" }]);
});

describe("LlmSettingsPanel", () => {
  it("shows only allowed providers as selectable for a member", async () => {
    render(<LlmSettingsPanel />);

    await waitFor(() =>
      expect(screen.getByText("providers.ollama")).toBeInTheDocument(),
    );
    expect(screen.queryByText("providers.external_api")).not.toBeInTheDocument();
    expect(screen.queryByText("allowedProviders")).not.toBeInTheDocument();
  });

  it("shows admin controls for an owner", async () => {
    apiMock.members.list.mockResolvedValue([{ user_id: 1, role: "OWNER" }]);
    apiMock.llm.settings.mockResolvedValue({
      allowed_providers: ["ollama"],
      default_provider: "ollama",
      model: null,
      external_configured: false,
      external_base_url: null,
      external_model: null,
    });

    render(<LlmSettingsPanel />);

    await waitFor(() =>
      expect(screen.getByText("allowedProviders")).toBeInTheDocument(),
    );
    expect(screen.getByText("externalSection")).toBeInTheDocument();
  });

  it("locks the stored api key until unlocked", async () => {
    apiMock.members.list.mockResolvedValue([{ user_id: 1, role: "OWNER" }]);
    apiMock.llm.settings.mockResolvedValue({
      allowed_providers: ["ollama", "external_api"],
      default_provider: "ollama",
      model: null,
      external_configured: true,
      external_base_url: "https://api.test/v1",
      external_model: "gpt-x",
    });

    render(<LlmSettingsPanel />);

    const locked = await screen.findByDisplayValue("*".repeat(12));
    expect(locked).toBeDisabled();

    fireEvent.click(screen.getByLabelText("editKey"));

    await waitFor(() =>
      expect(screen.queryByDisplayValue("*".repeat(12))).not.toBeInTheDocument(),
    );
  });
});
