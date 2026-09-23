import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock("@/features/auth/AuthProvider", () => ({
  useAuth: () => ({ user: { id: 1, email: "user@example.com" } }),
}));

vi.mock("@/features/workspaces/WorkspaceProvider", () => ({
  useWorkspace: () => ({ activeWorkspace: { id: 1 } }),
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

  it("sets the workspace default when an admin picks a provider", async () => {
    apiMock.members.list.mockResolvedValue([{ user_id: 1, role: "OWNER" }]);
    apiMock.llm.config.mockResolvedValue({
      providers: [
        { id: "ollama", enabled: true, models: ["llama3.2"] },
        { id: "external_api", enabled: true, models: ["gpt-x"] },
      ],
      allowed_providers: ["ollama", "external_api"],
      selected_provider: "ollama",
      default_provider: "ollama",
    });
    apiMock.llm.settings.mockResolvedValue({
      allowed_providers: ["ollama", "external_api"],
      default_provider: "ollama",
      model: null,
      external_configured: false,
      external_base_url: null,
      external_model: null,
    });
    apiMock.llm.selectProvider.mockResolvedValue({ selected_provider: "external_api" });
    apiMock.llm.updateSettings.mockResolvedValue({});

    render(<LlmSettingsPanel />);

    const [label] = await screen.findAllByText("providers.external_api");
    fireEvent.click(label.closest("label")!.querySelector("input")!);

    await waitFor(() =>
      expect(apiMock.llm.selectProvider).toHaveBeenCalledWith(1, "external_api"),
    );
    await waitFor(() =>
      expect(apiMock.llm.updateSettings).toHaveBeenCalledWith(1, {
        default_provider: "external_api",
      }),
    );
  });

  it("does not change the workspace default for a member", async () => {
    apiMock.members.list.mockResolvedValue([{ user_id: 1, role: "MEMBER" }]);
    apiMock.llm.config.mockResolvedValue({
      providers: [
        { id: "ollama", enabled: true, models: ["llama3.2"] },
        { id: "external_api", enabled: true, models: ["gpt-x"] },
      ],
      allowed_providers: ["ollama", "external_api"],
      selected_provider: "ollama",
      default_provider: "ollama",
    });
    apiMock.llm.selectProvider.mockResolvedValue({ selected_provider: "external_api" });

    render(<LlmSettingsPanel />);

    const [label] = await screen.findAllByText("providers.external_api");
    fireEvent.click(label.closest("label")!.querySelector("input")!);

    await waitFor(() =>
      expect(apiMock.llm.selectProvider).toHaveBeenCalledWith(1, "external_api"),
    );
    expect(apiMock.llm.updateSettings).not.toHaveBeenCalled();
  });

  it("shows a temporary saved confirmation after saving", async () => {
    apiMock.members.list.mockResolvedValue([{ user_id: 1, role: "OWNER" }]);
    apiMock.llm.settings.mockResolvedValue({
      allowed_providers: ["ollama"],
      default_provider: "ollama",
      model: null,
      external_configured: false,
      external_base_url: null,
      external_model: null,
    });
    apiMock.llm.updateSettings.mockResolvedValue({
      allowed_providers: ["ollama"],
      default_provider: "ollama",
      model: null,
      external_configured: false,
      external_base_url: null,
      external_model: null,
    });

    render(<LlmSettingsPanel />);
    const button = await screen.findByRole("button", { name: "save" });

    vi.useFakeTimers();
    await act(async () => {
      fireEvent.click(button);
    });

    expect(screen.getByRole("status")).toHaveTextContent("saved");

    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    vi.useRealTimers();
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
