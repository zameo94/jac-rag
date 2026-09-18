import { afterEach, describe, expect, it, vi } from "vitest";

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

describe("tenants api", () => {
  it("lists tenants", async () => {
    const fetchMock = mockFetch(200, [{ id: 1, name: "Acme" }]);
    vi.stubGlobal("fetch", fetchMock);

    const tenants = await api.tenants.list();

    expect(tenants).toHaveLength(1);
    expect(fetchMock.mock.calls[0][0]).toContain("/tenants");
  });

  it("creates a tenant sending a null slug when omitted", async () => {
    const fetchMock = mockFetch(201, { id: 1 });
    vi.stubGlobal("fetch", fetchMock);

    await api.tenants.create("Acme", "", "it");

    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({
      name: "Acme",
      slug: null,
      default_locale: "it",
    });
  });
});

describe("members api", () => {
  it("updates a member role with PATCH", async () => {
    const fetchMock = mockFetch(200, { id: 1, role: "ADMIN" });
    vi.stubGlobal("fetch", fetchMock);

    await api.members.updateRole(1, 2, "ADMIN");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/tenants/1/members/2");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body)).toEqual({ role: "ADMIN" });
  });

  it("removes a member with DELETE", async () => {
    const fetchMock = mockFetch(204, null);
    vi.stubGlobal("fetch", fetchMock);

    await api.members.remove(1, 2);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/tenants/1/members/2");
    expect(init.method).toBe("DELETE");
  });
});

describe("invitations api", () => {
  it("creates an invitation with the given role", async () => {
    const fetchMock = mockFetch(201, { token: "abc" });
    vi.stubGlobal("fetch", fetchMock);

    await api.invitations.create(1, "a@b.it", "ADMIN");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/tenants/1/invitations");
    expect(JSON.parse(init.body)).toEqual({ email: "a@b.it", role: "ADMIN" });
  });

  it("accepts an invitation", async () => {
    const fetchMock = mockFetch(200, { id: 1 });
    vi.stubGlobal("fetch", fetchMock);

    await api.invitations.accept("token-123");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/invitations/token-123/accept");
    expect(init.method).toBe("POST");
  });
});

describe("documents api", () => {
  it("lists documents for a tenant", async () => {
    const fetchMock = mockFetch(200, []);
    vi.stubGlobal("fetch", fetchMock);

    await api.documents.list(3);

    expect(fetchMock.mock.calls[0][0]).toContain("/tenants/3/documents");
  });

  it("fetches a single document status", async () => {
    const fetchMock = mockFetch(200, { id: 5, status: "ready" });
    vi.stubGlobal("fetch", fetchMock);

    const doc = await api.documents.get(3, 5);

    expect(doc.status).toBe("ready");
    expect(fetchMock.mock.calls[0][0]).toContain("/tenants/3/documents/5");
  });
});
