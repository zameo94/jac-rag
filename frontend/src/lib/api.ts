import { ApiError } from "./api-error";
import { tokenStore } from "./token-store";
import type {
  Document,
  InvitationCreated,
  Member,
  Membership,
  MembershipRole,
  Tenant,
  TokenPair,
  User,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL;

if (!API_BASE) {
  throw new Error("NEXT_PUBLIC_API_URL is not set");
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean;
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

  if (options.auth !== false) {
    const token = tokenStore.getAccess();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: options.method ?? "GET",
      headers,
      body,
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
        auth: false,
      });
    },
    login(email: string, password: string): Promise<TokenPair> {
      return request("/auth/login", {
        method: "POST",
        body: { email, password },
        auth: false,
      });
    },
    refresh(refreshToken: string): Promise<TokenPair> {
      return request("/auth/refresh", {
        method: "POST",
        body: { refresh_token: refreshToken },
        auth: false,
      });
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
};
