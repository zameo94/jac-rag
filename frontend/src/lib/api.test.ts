import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api-error";
import { api } from "@/lib/api";
import { tokenStore } from "@/lib/token-store";

function mockFetch(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: "status",
    json: async () => body,
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  tokenStore.clear();
});

describe("api client", () => {
  it("returns parsed json on success", async () => {
    vi.stubGlobal("fetch", mockFetch(200, { id: 1, email: "a@b.it" }));

    const user = await api.auth.me();

    expect(user).toEqual({ id: 1, email: "a@b.it" });
  });

  it("adds the bearer token when present", async () => {
    const fetchMock = mockFetch(200, { id: 1 });
    vi.stubGlobal("fetch", fetchMock);
    tokenStore.set("access-token", "refresh-token");

    await api.auth.me();

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer access-token");
  });

  it("does not add authorization for login", async () => {
    const fetchMock = mockFetch(200, { access_token: "a", refresh_token: "b" });
    vi.stubGlobal("fetch", fetchMock);
    tokenStore.set("access-token", "refresh-token");

    await api.auth.login("a@b.it", "password");

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers.Authorization).toBeUndefined();
  });

  it("throws ApiError with code from payload", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch(409, { code: "EMAIL_ALREADY_REGISTERED", message: "exists" }),
    );

    await expect(api.auth.register("a@b.it", "password", "it")).rejects.toMatchObject({
      code: "EMAIL_ALREADY_REGISTERED",
      status: 409,
    });
  });

  it("throws NETWORK_ERROR when fetch rejects", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("boom")));

    await expect(api.auth.me()).rejects.toMatchObject({ code: "NETWORK_ERROR" });
  });

  it("returns undefined for 204 responses", async () => {
    vi.stubGlobal("fetch", mockFetch(204, null));

    await expect(api.documents.remove(1, 2)).resolves.toBeUndefined();
  });

  it("sends multipart form data for uploads", async () => {
    const fetchMock = mockFetch(201, { id: 1 });
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["hello"], "a.txt", { type: "text/plain" });

    await api.documents.upload(1, file);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/tenants/1/documents");
    expect(init.body).toBeInstanceOf(FormData);
    expect(init.headers["Content-Type"]).toBeUndefined();
  });
});

describe("ApiError", () => {
  it("stores code, status and details", () => {
    const error = new ApiError(422, {
      code: "VALIDATION_ERROR",
      message: "invalid",
      details: [{ loc: ["body"] }],
    });

    expect(error.code).toBe("VALIDATION_ERROR");
    expect(error.status).toBe(422);
    expect(error.message).toBe("invalid");
    expect(error.details).toEqual([{ loc: ["body"] }]);
  });
});
