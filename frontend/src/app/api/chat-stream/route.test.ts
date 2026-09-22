// @vitest-environment node

import { afterEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";

import { POST } from "@/app/api/chat-stream/route";

const BASE = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

function makeRequest(tenantId = "7"): NextRequest {
  return {
    method: "POST",
    nextUrl: new URL(`http://localhost:3000/api/chat-stream?tenantId=${tenantId}`),
    headers: new Headers({
      "content-type": "application/json",
      cookie: "jacrag_access=token",
      host: "localhost:3000",
      "accept-encoding": "gzip",
      "x-evil": "1",
    }),
    body: "{\"message\":\"hi\"}",
  } as unknown as NextRequest;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("chat stream route handler", () => {
  it("streams the upstream body and forwards auth without hop-by-hop headers", async () => {
    const sse = "event: sources\ndata: {}\n\nevent: done\ndata: {}\n\n";
    const upstreamBody = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(sse));
        controller.close();
      },
    });
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(upstreamBody, {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(makeRequest());

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/api/v1/tenants/7/chat/stream`);
    const sent = init.headers as Headers;
    expect(sent.get("cookie")).toBe("jacrag_access=token");
    expect(sent.get("content-type")).toBe("application/json");
    expect(sent.get("host")).toBeNull();
    expect(sent.get("accept-encoding")).toBeNull();
    expect(sent.get("x-evil")).toBeNull();

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("text/event-stream");
    expect(response.headers.get("cache-control")).toContain("no-cache");
    expect(response.headers.get("x-accel-buffering")).toBe("no");
    expect(await response.text()).toBe(sse);
  });

  it("rejects a request without tenantId", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const request = {
      nextUrl: new URL("http://localhost:3000/api/chat-stream"),
      headers: new Headers(),
    } as unknown as NextRequest;

    const response = await POST(request);

    expect(response.status).toBe(422);
    expect(await response.json()).toEqual({
      code: "VALIDATION_ERROR",
      message: "tenantId is required",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("passes through a pre-stream error status and JSON body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ code: "NOT_A_MEMBER", message: "no" }), {
          status: 403,
          headers: { "content-type": "application/json" },
        }),
      ),
    );

    const response = await POST(makeRequest());

    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({ code: "NOT_A_MEMBER", message: "no" });
  });
});
