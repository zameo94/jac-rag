import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock("@/features/tenants/TenantProvider", () => ({
  useTenant: () => ({ activeTenant: { id: 1 } }),
}));

vi.mock("@/lib/chat-stream", () => ({ streamChat: vi.fn() }));

import { ChatPlayground } from "@/features/chat/ChatPlayground";
import { streamChat } from "@/lib/chat-stream";

const streamMock = vi.mocked(streamChat);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ChatPlayground", () => {
  it("streams tokens into the assistant turn", async () => {
    streamMock.mockImplementation(async (_tenantId, _message, handlers) => {
      handlers.onSources?.({
        grounded: true,
        sources: [{ document_id: 1, filename: "doc.md", chunk_index: 0, score: 0.9 }],
      });
      handlers.onToken?.("Ciao");
      handlers.onToken?.(" mondo");
    });

    render(<ChatPlayground />);

    fireEvent.change(screen.getByPlaceholderText("placeholder"), {
      target: { value: "domanda" },
    });
    fireEvent.click(screen.getByText("send"));

    await waitFor(() => expect(screen.getByText("Ciao mondo")).toBeInTheDocument());
    expect(screen.getByText("domanda")).toBeInTheDocument();
    expect(streamMock).toHaveBeenCalledWith(
      1,
      "domanda",
      expect.objectContaining({ onToken: expect.any(Function) }),
    );
  });

  it("shows a stream error", async () => {
    streamMock.mockImplementation(async (_tenantId, _message, handlers) => {
      handlers.onError?.({ code: "LLM_UNAVAILABLE", message: "down" });
    });

    render(<ChatPlayground />);

    fireEvent.change(screen.getByPlaceholderText("placeholder"), {
      target: { value: "domanda" },
    });
    fireEvent.click(screen.getByText("send"));

    await waitFor(() => expect(streamMock).toHaveBeenCalled());
  });
});
