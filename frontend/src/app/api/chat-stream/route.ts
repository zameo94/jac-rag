import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const API_PROXY_TARGET = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

const FORWARDED_REQUEST_HEADERS = [
  "cookie",
  "content-type",
  "accept",
  "accept-language",
  "authorization",
];

export async function POST(request: NextRequest): Promise<Response> {
  const tenantId = request.nextUrl.searchParams.get("tenantId");
  if (!tenantId) {
    return Response.json(
      { code: "VALIDATION_ERROR", message: "tenantId is required" },
      { status: 422 },
    );
  }

  const target = `${API_PROXY_TARGET}/api/v1/tenants/${encodeURIComponent(tenantId)}/chat/stream`;

  const headers = new Headers();
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }

  const upstream = await fetch(target, {
    method: "POST",
    headers,
    body: request.body,
    duplex: "half",
  } as RequestInit & { duplex: "half" });

  const responseHeaders = new Headers();
  const contentType = upstream.headers.get("content-type");
  if (contentType) responseHeaders.set("content-type", contentType);
  responseHeaders.set("cache-control", "no-cache, no-transform");
  responseHeaders.set("x-accel-buffering", "no");

  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}
