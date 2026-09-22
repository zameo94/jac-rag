import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next-intl", () => ({
  useTranslations: () => Object.assign((key: string) => key, { has: () => true }),
}));

vi.mock("@/features/tenants/TenantProvider", () => ({
  useTenant: () => ({ activeTenant: { id: 1 } }),
}));

vi.mock("@/lib/chat-stream", () => ({ streamChat: vi.fn() }));

import { ChatPlayground } from "@/features/chat/ChatPlayground";
import { streamChat } from "@/lib/chat-stream";

import { ApiError } from "@/lib/api-error";
import type { ChatStreamHandlers } from "@/lib/chat-stream";

const streamMock = vi.mocked(streamChat);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ChatPlayground", () => {
  it("streams tokens into the assistant turn", async () => {
    streamMock.mockImplementation(async (_tenantId, _message, handlers) => {
      handlers.onSources?.({
        conversation_id: 7,
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
      null,
    );
  });

  it("shows a stream error", async () => {
    streamMock.mockImplementation(async (_tenantId, _message, handlers) => {
      handlers.onError?.({ code: "LLM_UNAVAILABLE", message: "down" });
    });

    const { container } = render(<ChatPlayground />);

    fireEvent.change(screen.getByPlaceholderText("placeholder"), {
      target: { value: "domanda" },
    });
    fireEvent.click(screen.getByText("send"));

    await waitFor(() => expect(streamMock).toHaveBeenCalled());
    expect(screen.getByText("domanda")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("LLM_UNAVAILABLE");
    expect(container.querySelectorAll(".bg-emerald-50")).toHaveLength(0);
  });

  it("shows an error when the stream is interrupted without completion", async () => {
    streamMock.mockRejectedValue(
      new ApiError(0, { code: "STREAM_INCOMPLETE", message: "ended" }),
    );

    const { container } = render(<ChatPlayground />);

    fireEvent.change(screen.getByPlaceholderText("placeholder"), {
      target: { value: "domanda" },
    });
    fireEvent.click(screen.getByText("send"));

    await waitFor(() => expect(streamMock).toHaveBeenCalled());
    expect(screen.getByRole("alert")).toHaveTextContent("STREAM_INCOMPLETE");
    expect(container.querySelectorAll(".bg-emerald-50")).toHaveLength(0);
  });

  it("shows a searching hint before the sources arrive", async () => {
    let receivedHandlers: ChatStreamHandlers | undefined;
    streamMock.mockImplementation(
      (_tenantId, _message, handlers) =>
        new Promise<never>(() => {
          receivedHandlers = handlers;
        }),
    );

    render(<ChatPlayground />);

    fireEvent.change(screen.getByPlaceholderText("placeholder"), {
      target: { value: "domanda" },
    });
    fireEvent.click(screen.getByText("send"));

    await waitFor(() => expect(streamMock).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText("searching")).toBeInTheDocument());

    receivedHandlers?.onSources?.({ conversation_id: 7, grounded: true, sources: [] });
    await waitFor(() => expect(screen.queryByText("searching")).toBeNull());
  });

  it("reuses the conversation id on subsequent sends", async () => {
    let calls = 0;
    streamMock.mockImplementation(async (_tenantId, _message, handlers) => {
      calls += 1;
      if (calls === 1) {
        handlers.onSources?.({ conversation_id: 7, grounded: true, sources: [] });
      }
      handlers.onToken?.("ok");
    });

    render(<ChatPlayground />);
    const input = screen.getByPlaceholderText("placeholder");

    fireEvent.change(input, { target: { value: "primo" } });
    fireEvent.click(screen.getByText("send"));
    await waitFor(() => expect(streamMock).toHaveBeenCalledTimes(1));

    fireEvent.change(input, { target: { value: "secondo" } });
    fireEvent.click(screen.getByText("send"));
    await waitFor(() => expect(streamMock).toHaveBeenCalledTimes(2));

    const [first, second] = streamMock.mock.calls;
    expect(first[3]).toBeNull();
    expect(second[3]).toBe(7);
  });
});
