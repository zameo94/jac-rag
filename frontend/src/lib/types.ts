export type MembershipRole = "OWNER" | "ADMIN" | "MEMBER";
export type AnswerMode = "strict" | "assistive";
export type DocumentStatus = "pending" | "processing" | "ready" | "failed";

export interface User {
  id: number;
  email: string;
  locale: string;
  is_active: boolean;
}

export interface Workspace {
  id: number;
  name: string;
  slug: string;
  default_locale: string;
  answer_mode: AnswerMode;
  is_active: boolean;
}

export interface WorkspaceUpdate {
  name?: string;
  slug?: string;
  default_locale?: string;
  answer_mode?: AnswerMode;
  is_active?: boolean;
}

export interface Member {
  id: number;
  user_id: number;
  workspace_id: number;
  role: MembershipRole;
  email: string;
  created_at: string;
}

export interface InvitationCreated {
  id: number;
  workspace_id: number;
  email: string;
  role: MembershipRole;
  token: string;
  expires_at: string;
}

export interface Membership {
  id: number;
  user_id: number;
  workspace_id: number;
  role: MembershipRole;
}

export interface Document {
  id: number;
  workspace_id: number;
  uploader_id: number;
  filename: string;
  mime: string;
  size: number;
  language: string | null;
  status: DocumentStatus;
  error: string | null;
  chunk_count: number | null;
}

export interface ApiErrorPayload {
  code: string;
  message: string;
  details?: unknown;
}

export interface LLMProviderInfo {
  id: string;
  enabled: boolean;
  models: string[];
}

export interface LLMConfig {
  providers: LLMProviderInfo[];
  allowed_providers: string[];
  selected_provider: string | null;
  default_provider: string;
}

export interface LLMSettings {
  allowed_providers: string[];
  default_provider: string | null;
  model: string | null;
  external_configured: boolean;
  external_base_url: string | null;
  external_model: string | null;
}

export interface LLMSettingsUpdate {
  allowed_providers?: string[];
  default_provider?: string;
  model?: string;
  external_base_url?: string;
  external_model?: string;
  external_api_key?: string;
}

export interface ProviderSelection {
  selected_provider: string;
}

export interface ApiKey {
  id: number;
  workspace_id: number;
  name: string;
  prefix: string;
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
}

export interface ApiKeyCreated extends ApiKey {
  key: string;
}

export interface ChatSource {
  document_id: number;
  filename: string;
  chunk_index: number;
  score: number;
}

export interface ChatResponse {
  conversation_id: number;
  answer: string;
  provider: string;
  model: string;
  grounded: boolean;
  sources: ChatSource[];
}

export type MessageRole = "user" | "assistant";

export interface ChatMessage {
  id: number;
  conversation_id: number;
  role: MessageRole;
  content: string;
  provider: string | null;
  model: string | null;
  grounded: boolean | null;
  error_code: string | null;
  sources: ChatSource[] | null;
  created_at: string;
}

export interface Conversation {
  id: number;
  workspace_id: number;
  user_id: number | null;
  end_user_id: string | null;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: ChatMessage[];
}
