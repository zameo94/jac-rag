import { ApiError } from "./api-error";
import { touchSession } from "./session-idle";
import type {
  AnswerMode,
  ApiKey,
  ApiKeyCreated,
  ChatResponse,
  Conversation,
  ConversationDetail,
  Document,
  InvitationCreated,
  LLMConfig,
  LLMSettings,
  LLMSettingsUpdate,
  Member,
  Membership,
  MembershipRole,
  ProviderSelection,
  Workspace,
  WorkspaceUpdate,
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
  touchSession();
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
  workspaces: {
    list(): Promise<Workspace[]> {
      return request("/workspaces");
    },
    get(workspaceId: number): Promise<Workspace> {
      return request(`/workspaces/${workspaceId}`);
    },
    create(
      name: string,
      slug: string | undefined,
      defaultLocale: string,
      answerMode: AnswerMode,
    ): Promise<Workspace> {
      return request("/workspaces", {
        method: "POST",
        body: {
          name,
          slug: slug || null,
          default_locale: defaultLocale,
          answer_mode: answerMode,
        },
      });
    },
    update(workspaceId: number, body: WorkspaceUpdate): Promise<Workspace> {
      return request(`/workspaces/${workspaceId}`, { method: "PATCH", body });
    },
    remove(workspaceId: number): Promise<void> {
      return request(`/workspaces/${workspaceId}`, { method: "DELETE" });
    },
  },
  members: {
    me(workspaceId: number): Promise<Membership> {
      return request(`/workspaces/${workspaceId}/me`);
    },
    list(workspaceId: number): Promise<Member[]> {
      return request(`/workspaces/${workspaceId}/members`);
    },
    updateRole(workspaceId: number, userId: number, role: MembershipRole): Promise<Member> {
      return request(`/workspaces/${workspaceId}/members/${userId}`, {
        method: "PATCH",
        body: { role },
      });
    },
    remove(workspaceId: number, userId: number): Promise<void> {
      return request(`/workspaces/${workspaceId}/members/${userId}`, { method: "DELETE" });
    },
  },
  invitations: {
    create(
      workspaceId: number,
      email: string,
      role: MembershipRole = "MEMBER",
    ): Promise<InvitationCreated> {
      return request(`/workspaces/${workspaceId}/invitations`, {
        method: "POST",
        body: { email, role },
      });
    },
    accept(token: string): Promise<Membership> {
      return request(`/invitations/${token}/accept`, { method: "POST" });
    },
  },
  documents: {
    list(workspaceId: number): Promise<Document[]> {
      return request(`/workspaces/${workspaceId}/documents`);
    },
    get(workspaceId: number, documentId: number): Promise<Document> {
      return request(`/workspaces/${workspaceId}/documents/${documentId}`);
    },
    upload(workspaceId: number, file: File): Promise<Document> {
      const formData = new FormData();
      formData.append("file", file);
      return request(`/workspaces/${workspaceId}/documents`, { method: "POST", formData });
    },
    remove(workspaceId: number, documentId: number): Promise<void> {
      return request(`/workspaces/${workspaceId}/documents/${documentId}`, { method: "DELETE" });
    },
  },
  llm: {
    config(workspaceId: number): Promise<LLMConfig> {
      return request(`/workspaces/${workspaceId}/llm/config`);
    },
    settings(workspaceId: number): Promise<LLMSettings> {
      return request(`/workspaces/${workspaceId}/llm/settings`);
    },
    updateSettings(workspaceId: number, body: LLMSettingsUpdate): Promise<LLMSettings> {
      return request(`/workspaces/${workspaceId}/llm/settings`, { method: "PUT", body });
    },
    selectProvider(workspaceId: number, providerId: string): Promise<ProviderSelection> {
      return request(`/workspaces/${workspaceId}/llm/provider`, {
        method: "PUT",
        body: { provider_id: providerId },
      });
    },
  },
  apiKeys: {
    list(workspaceId: number): Promise<ApiKey[]> {
      return request(`/workspaces/${workspaceId}/api-keys`);
    },
    create(workspaceId: number, name: string): Promise<ApiKeyCreated> {
      return request(`/workspaces/${workspaceId}/api-keys`, { method: "POST", body: { name } });
    },
    setActive(workspaceId: number, keyId: number, isActive: boolean): Promise<ApiKey> {
      return request(`/workspaces/${workspaceId}/api-keys/${keyId}`, {
        method: "PATCH",
        body: { is_active: isActive },
      });
    },
  },
  chat: {
    send(
      workspaceId: number,
      message: string,
      conversationId?: number | null,
    ): Promise<ChatResponse> {
      return request(`/workspaces/${workspaceId}/chat`, {
        method: "POST",
        body: { message, conversation_id: conversationId ?? null },
      });
    },
  },
  conversations: {
    list(workspaceId: number): Promise<Conversation[]> {
      return request(`/workspaces/${workspaceId}/conversations`);
    },
    get(workspaceId: number, conversationId: number): Promise<ConversationDetail> {
      return request(`/workspaces/${workspaceId}/conversations/${conversationId}`);
    },
    remove(workspaceId: number, conversationId: number): Promise<void> {
      return request(`/workspaces/${workspaceId}/conversations/${conversationId}`, {
        method: "DELETE",
      });
    },
  },
};
