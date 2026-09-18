export type MembershipRole = "OWNER" | "ADMIN" | "MEMBER";
export type AnswerMode = "strict" | "assistive";
export type DocumentStatus = "pending" | "processing" | "ready" | "failed";

export interface User {
  id: number;
  email: string;
  locale: string;
  is_active: boolean;
}

export interface Tenant {
  id: number;
  name: string;
  slug: string;
  default_locale: string;
  answer_mode: AnswerMode;
}

export interface Member {
  id: number;
  user_id: number;
  tenant_id: number;
  role: MembershipRole;
  email: string;
  created_at: string;
}

export interface InvitationCreated {
  id: number;
  tenant_id: number;
  email: string;
  role: MembershipRole;
  token: string;
  expires_at: string;
}

export interface Membership {
  id: number;
  user_id: number;
  tenant_id: number;
  role: MembershipRole;
}

export interface Document {
  id: number;
  tenant_id: number;
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
