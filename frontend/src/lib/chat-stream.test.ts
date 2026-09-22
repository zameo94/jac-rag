import { afterEach, describe, expect, it, vi } from "vitest";

import { parseSseChunk, streamChat } from "@/lib/chat-stream";

afterEach(() => {
  vi.restoreAllMocks();
});

function streamResponse(chunks: string[]) {
  const encoder = new TextEncoder();
  const body = new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return { ok: true, status: 200, statusText: "OK", body };
}

describe("parseSseChunk", () => {
  it("parses complete events and keeps the partial remainder", () => {
    const { events, rest } = parseSseChunk(
      'event: token\ndata: {"text":"Hi"}\n\nevent: done\ndata: {"provider":"ollama"}\n\nevent: tok',
    );

    expect(events).toEqual([
      { event: "token", data: { text: "Hi" } },
      { event: "done", data: { provider: "ollama" } },
    ]);
    expect(rest).toBe("event: tok");
  });
});

describe("streamChat", () => {
  it("dispatches sources, tokens and done", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        streamResponse([
          'event: sources\ndata: {"conversation_id":7,"grounded":true,"sources":[{"filename":"a.md"}]}\n\n',
          'event: token\ndata: {"text":"Ciao"}\n\n',
          'event: token\ndata: {"text":" mondo"}\n\n',
          'event: done\ndata: {"provider":"ollama","model":"m","grounded":true}\n\n',
        ]),
      ),
    );
    const tokens: string[] = [];
    const onSources = vi.fn();
    const onDone = vi.fn();

    await streamChat(1, "hi", {
      onToken: (text) => tokens.push(text),
      onSources,
      onDone,
    });

    expect(tokens.join("")).toBe("Ciao mondo");
    expect(onSources).toHaveBeenCalledWith({
      conversation_id: 7,
      grounded: true,
      sources: [{ filename: "a.md" }],
    });
    expect(onDone).toHaveBeenCalledWith({
      provider: "ollama",
      model: "m",
      grounded: true,
    });
  });

  it("throws an ApiError on a failed response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 429,
        statusText: "Too Many Requests",
        json: async () => ({ code: "RATE_LIMITED", message: "no" }),
      }),
    );

    await expect(streamChat(1, "hi", {})).rejects.toMatchObject({ status: 429 });
  });

  it("rejects with STREAM_INCOMPLETE when the stream ends without done or error", async () => {
    const onSources = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        streamResponse([
          'event: sources\ndata: {"conversation_id":7,"grounded":true,"sources":[]}\n\n',
        ]),
      ),
    );

    await expect(
      streamChat(1, "hi", { onSources }),
    ).rejects.toMatchObject({ code: "STREAM_INCOMPLETE" });
    expect(onSources).toHaveBeenCalledTimes(1);
  });

  it("resolves after an error event without requiring done", async () => {
    const onError = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        streamResponse([
          'event: sources\ndata: {"conversation_id":7,"grounded":true,"sources":[]}\n\n',
          'event: error\ndata: {"code":"LLM_UNAVAILABLE","message":"down"}\n\n',
        ]),
      ),
    );

    await streamChat(1, "hi", { onError });

    expect(onError).toHaveBeenCalledWith({ code: "LLM_UNAVAILABLE", message: "down" });
  });

  it("wraps a mid-stream read failure as NETWORK_ERROR", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        statusText: "OK",
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode("event: sources"));
            controller.error(new Error("connection reset"));
          },
        }),
      }),
    );

    await expect(streamChat(1, "hi", {})).rejects.toMatchObject({
      code: "NETWORK_ERROR",
    });
  });
});
