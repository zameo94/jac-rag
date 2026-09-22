import { ApiError } from "./api-error";
import type { ChatSource } from "./types";

export interface ChatStreamHandlers {
  onSources?: (payload: {
    conversation_id: number;
    grounded: boolean;
    sources: ChatSource[];
  }) => void;
  onToken?: (text: string) => void;
  onDone?: (payload: { provider: string; model: string; grounded: boolean }) => void;
  onError?: (payload: { code: string; message: string }) => void;
}

interface ParsedEvent {
  event: string;
  data: Record<string, unknown>;
}

export function parseSseChunk(buffer: string): { events: ParsedEvent[]; rest: string } {
  const events: ParsedEvent[] = [];
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";

  for (const part of parts) {
    const lines = part.split("\n");
    const eventLine = lines.find((line) => line.startsWith("event: "));
    if (!eventLine) continue;
    const dataLines = lines
      .filter((line) => line.startsWith("data: "))
      .map((line) => line.slice("data: ".length));
    let data: Record<string, unknown> = {};
    if (dataLines.length > 0) {
      try {
        data = JSON.parse(dataLines.join("\n"));
      } catch {
        data = {};
      }
    }
    events.push({ event: eventLine.slice("event: ".length), data });
  }

  return { events, rest };
}

function dispatch(event: ParsedEvent, handlers: ChatStreamHandlers): void {
  if (event.event === "sources") {
    handlers.onSources?.(
      event.data as {
        conversation_id: number;
        grounded: boolean;
        sources: ChatSource[];
      },
    );
  } else if (event.event === "token") {
    handlers.onToken?.(String(event.data.text ?? ""));
  } else if (event.event === "done") {
    handlers.onDone?.(
      event.data as { provider: string; model: string; grounded: boolean },
    );
  } else if (event.event === "error") {
    handlers.onError?.(event.data as { code: string; message: string });
  }
}

export async function streamChat(
  tenantId: number,
  message: string,
  handlers: ChatStreamHandlers,
  conversationId?: number | null,
): Promise<void> {
  const response = await fetch(
    `/api/chat-stream?tenantId=${encodeURIComponent(String(tenantId))}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ message, conversation_id: conversationId ?? null }),
    },
  );

  if (!response.ok) {
    let payload = { code: "HTTP_ERROR", message: response.statusText };
    try {
      const data = await response.json();
      if (data && typeof data.code === "string") payload = data;
    } catch {
      // keep fallback payload
    }
    throw new ApiError(response.status, payload);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new ApiError(0, { code: "NETWORK_ERROR", message: "No response body" });
  }

  const decoder = new TextDecoder();
  let buffer = "";
  let finished = false;
  const markFinished = (event: ParsedEvent) => {
    if (event.event === "done" || event.event === "error") finished = true;
  };
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parsed = parseSseChunk(buffer);
      buffer = parsed.rest;
      for (const event of parsed.events) {
        dispatch(event, handlers);
        markFinished(event);
      }
    }
  if (buffer.trim()) {
    const parsed = parseSseChunk(`${buffer}\n\n`);
    for (const event of parsed.events) {
      dispatch(event, handlers);
      markFinished(event);
    }
  }
  if (!finished) {
    throw new ApiError(0, {
      code: "STREAM_INCOMPLETE",
      message: "The connection ended before the answer completed.",
    });
  }
} catch (err) {
  if (err instanceof ApiError) throw err;
  throw new ApiError(0, {
    code: "NETWORK_ERROR",
    message: "The connection was interrupted.",
  });
}
}
