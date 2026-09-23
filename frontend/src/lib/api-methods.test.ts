import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

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
});

describe("workspaces api", () => {
  it("lists workspaces", async () => {
    const fetchMock = mockFetch(200, [{ id: 1, name: "Acme" }]);
    vi.stubGlobal("fetch", fetchMock);

    const workspaces = await api.workspaces.list();

    expect(workspaces).toHaveLength(1);
    expect(fetchMock.mock.calls[0][0]).toContain("/workspaces");
  });

  it("creates a workspace sending a null slug when omitted", async () => {
    const fetchMock = mockFetch(201, { id: 1 });
    vi.stubGlobal("fetch", fetchMock);

    await api.workspaces.create("Acme", "", "it", "assistive");

    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({
      name: "Acme",
      slug: null,
      default_locale: "it",
      answer_mode: "assistive",
    });
  });

  it("updates a workspace", async () => {
    const fetchMock = mockFetch(200, { id: 1 });
    vi.stubGlobal("fetch", fetchMock);

    await api.workspaces.update(1, { name: "New", slug: "new" });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/workspaces/1");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body)).toEqual({ name: "New", slug: "new" });
  });

  it("deletes a workspace", async () => {
    const fetchMock = mockFetch(204, null);
    vi.stubGlobal("fetch", fetchMock);

    await api.workspaces.remove(1);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/workspaces/1");
    expect(init.method).toBe("DELETE");
  });
});

describe("members api", () => {
  it("fetches the current membership", async () => {
    const fetchMock = mockFetch(200, {
      id: 3,
      user_id: 1,
      workspace_id: 2,
      role: "ADMIN",
    });
    vi.stubGlobal("fetch", fetchMock);

    const membership = await api.members.me(2);

    expect(membership.role).toBe("ADMIN");
    expect(fetchMock.mock.calls[0][0]).toContain("/workspaces/2/me");
  });

  it("updates a member role with PATCH", async () => {
    const fetchMock = mockFetch(200, { id: 1, role: "ADMIN" });
    vi.stubGlobal("fetch", fetchMock);

    await api.members.updateRole(1, 2, "ADMIN");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/workspaces/1/members/2");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body)).toEqual({ role: "ADMIN" });
  });

  it("removes a member with DELETE", async () => {
    const fetchMock = mockFetch(204, null);
    vi.stubGlobal("fetch", fetchMock);

    await api.members.remove(1, 2);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/workspaces/1/members/2");
    expect(init.method).toBe("DELETE");
  });
});

describe("invitations api", () => {
  it("creates an invitation with the given role", async () => {
    const fetchMock = mockFetch(201, { token: "abc" });
    vi.stubGlobal("fetch", fetchMock);

    await api.invitations.create(1, "a@b.it", "ADMIN");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/workspaces/1/invitations");
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
  it("lists documents for a workspace", async () => {
    const fetchMock = mockFetch(200, []);
    vi.stubGlobal("fetch", fetchMock);

    await api.documents.list(3);

    expect(fetchMock.mock.calls[0][0]).toContain("/workspaces/3/documents");
  });

  it("fetches a single document status", async () => {
    const fetchMock = mockFetch(200, { id: 5, status: "ready" });
    vi.stubGlobal("fetch", fetchMock);

    const doc = await api.documents.get(3, 5);

    expect(doc.status).toBe("ready");
    expect(fetchMock.mock.calls[0][0]).toContain("/workspaces/3/documents/5");
  });
});

describe("llm api", () => {
  it("fetches the llm config", async () => {
    const fetchMock = mockFetch(200, {
      providers: [],
      allowed_providers: [],
      selected_provider: null,
      default_provider: "ollama",
    });
    vi.stubGlobal("fetch", fetchMock);

    await api.llm.config(2);

    expect(fetchMock.mock.calls[0][0]).toContain("/workspaces/2/llm/config");
  });

  it("updates llm settings with PUT", async () => {
    const fetchMock = mockFetch(200, { allowed_providers: ["ollama"] });
    vi.stubGlobal("fetch", fetchMock);

    await api.llm.updateSettings(2, { allowed_providers: ["ollama"] });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/workspaces/2/llm/settings");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body)).toEqual({ allowed_providers: ["ollama"] });
  });

  it("selects a provider with PUT", async () => {
    const fetchMock = mockFetch(200, { selected_provider: "external_api" });
    vi.stubGlobal("fetch", fetchMock);

    await api.llm.selectProvider(2, "external_api");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/workspaces/2/llm/provider");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body)).toEqual({ provider_id: "external_api" });
  });
});

describe("api keys api", () => {
  it("creates an embed key", async () => {
    const fetchMock = mockFetch(201, { id: 1, key: "jrk_x" });
    vi.stubGlobal("fetch", fetchMock);

    await api.apiKeys.create(3, "Widget");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/workspaces/3/api-keys");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ name: "Widget" });
  });

  it("toggles a key with PATCH", async () => {
    const fetchMock = mockFetch(200, { id: 1, is_active: false });
    vi.stubGlobal("fetch", fetchMock);

    await api.apiKeys.setActive(3, 1, false);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/workspaces/3/api-keys/1");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body)).toEqual({ is_active: false });
  });
});

describe("conversations api", () => {
  it("lists workspace conversations", async () => {
    const fetchMock = mockFetch(200, []);
    vi.stubGlobal("fetch", fetchMock);

    await api.conversations.list(3);

    expect(fetchMock.mock.calls[0][0]).toContain("/workspaces/3/conversations");
  });

  it("deletes a conversation", async () => {
    const fetchMock = mockFetch(204, null);
    vi.stubGlobal("fetch", fetchMock);

    await api.conversations.remove(3, 9);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/workspaces/3/conversations/9");
    expect(init.method).toBe("DELETE");
  });
});

describe("chat api", () => {
  it("sends a chat message as JSON", async () => {
    const fetchMock = mockFetch(200, { answer: "ok" });
    vi.stubGlobal("fetch", fetchMock);

    await api.chat.send(3, "ciao", 5);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/workspaces/3/chat");
    expect(JSON.parse(init.body)).toEqual({ message: "ciao", conversation_id: 5 });
  });
});

describe("auth api", () => {
  it("refreshes the session without a body", async () => {
    const fetchMock = mockFetch(200, { id: 1 });
    vi.stubGlobal("fetch", fetchMock);

    await api.auth.refresh();

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/auth/refresh");
    expect(init.method).toBe("POST");
    expect(init.body).toBeUndefined();
  });

  it("logs out with POST", async () => {
    const fetchMock = mockFetch(204, null);
    vi.stubGlobal("fetch", fetchMock);

    await api.auth.logout();

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/auth/logout");
    expect(init.method).toBe("POST");
  });
});
