import { ApiError } from "./api-error";
import type {
  Document,
  InvitationCreated,
  LLMConfig,
  LLMSettings,
  LLMSettingsUpdate,
  Member,
  Membership,
  MembershipRole,
  ProviderSelection,
  Tenant,
  User,
} from "./types";

const API_BASE = "/api/v1";

interface RequestOptions {
  method?: string;
  body?: unknown;
  formData?: FormData;
}

async function parseError(response: Response): Promise<ApiError> {
  let payload = { code: "HTTP_ERROR", message: response.statusText };
  try {
    const data = await response.json();
    if (data && typeof data.code === "string") {
      payload = data;
    }
  } catch {
    // keep fallback payload
  }
  return new ApiError(response.status, payload);
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;

  if (options.formData) {
    body = options.formData;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: options.method ?? "GET",
      headers,
      body,
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError(0, { code: "NETWORK_ERROR", message: "Network error" });
  }

  if (response.status === 204) {
    return undefined as T;
  }

  if (!response.ok) {
    throw await parseError(response);
  }

  return (await response.json()) as T;
}

export const api = {
  auth: {
    register(email: string, password: string, locale: string): Promise<User> {
      return request("/auth/register", {
        method: "POST",
        body: { email, password, locale },
      });
    },
    login(email: string, password: string): Promise<User> {
      return request("/auth/login", { method: "POST", body: { email, password } });
    },
    refresh(): Promise<User> {
      return request("/auth/refresh", { method: "POST" });
    },
    logout(): Promise<void> {
      return request("/auth/logout", { method: "POST" });
    },
    me(): Promise<User> {
      return request("/auth/me");
    },
  },
  tenants: {
    list(): Promise<Tenant[]> {
      return request("/tenants");
    },
    get(tenantId: number): Promise<Tenant> {
      return request(`/tenants/${tenantId}`);
    },
    create(name: string, slug?: string, defaultLocale?: string): Promise<Tenant> {
      return request("/tenants", {
        method: "POST",
        body: { name, slug: slug || null, default_locale: defaultLocale },
      });
    },
  },
  members: {
    list(tenantId: number): Promise<Member[]> {
      return request(`/tenants/${tenantId}/members`);
    },
    updateRole(tenantId: number, userId: number, role: MembershipRole): Promise<Member> {
      return request(`/tenants/${tenantId}/members/${userId}`, {
        method: "PATCH",
        body: { role },
      });
    },
    remove(tenantId: number, userId: number): Promise<void> {
      return request(`/tenants/${tenantId}/members/${userId}`, { method: "DELETE" });
    },
  },
  invitations: {
    create(
      tenantId: number,
      email: string,
      role: MembershipRole = "MEMBER",
    ): Promise<InvitationCreated> {
      return request(`/tenants/${tenantId}/invitations`, {
        method: "POST",
        body: { email, role },
      });
    },
    accept(token: string): Promise<Membership> {
      return request(`/invitations/${token}/accept`, { method: "POST" });
    },
  },
  documents: {
    list(tenantId: number): Promise<Document[]> {
      return request(`/tenants/${tenantId}/documents`);
    },
    get(tenantId: number, documentId: number): Promise<Document> {
      return request(`/tenants/${tenantId}/documents/${documentId}`);
    },
    upload(tenantId: number, file: File): Promise<Document> {
      const formData = new FormData();
      formData.append("file", file);
      return request(`/tenants/${tenantId}/documents`, { method: "POST", formData });
    },
    remove(tenantId: number, documentId: number): Promise<void> {
      return request(`/tenants/${tenantId}/documents/${documentId}`, { method: "DELETE" });
    },
  },
  llm: {
    config(tenantId: number): Promise<LLMConfig> {
      return request(`/tenants/${tenantId}/llm/config`);
    },
    settings(tenantId: number): Promise<LLMSettings> {
      return request(`/tenants/${tenantId}/llm/settings`);
    },
    updateSettings(tenantId: number, body: LLMSettingsUpdate): Promise<LLMSettings> {
      return request(`/tenants/${tenantId}/llm/settings`, { method: "PUT", body });
    },
    selectProvider(tenantId: number, providerId: string): Promise<ProviderSelection> {
      return request(`/tenants/${tenantId}/llm/provider`, {
        method: "PUT",
        body: { provider_id: providerId },
      });
    },
  },
};
