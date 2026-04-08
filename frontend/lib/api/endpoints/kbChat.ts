import { apiClient } from "../client";

export interface KbChatRequest {
  query: string;
  knowledge_base_id?: number | null;
  category_id?: number | null;
  session_id?: string | null;
}

export interface RetrievedDoc {
  content: string;
  metadata?: {
    document_id?: number;
    document_title?: string;
    chunk_index?: number;
    score?: number;
    rerank_score?: number;
    category_id?: number | null;
    category_name?: string | null;
    source_path?: string | null;
  };
}

export interface KbChatResponse {
  answer: string;
  retrieved_docs: RetrievedDoc[];
  session_id?: string | null;
}

export interface KbChatSessionMessage {
  role: string;
  content: string;
  created_at: string;
}

export interface KbChatSessionSummary {
  session_id: string;
  title: string;
  preview?: string | null;
  knowledge_base_id?: number | null;
  knowledge_base_name?: string | null;
  category_id?: number | null;
  category_name?: string | null;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface KbChatSessionDetail extends KbChatSessionSummary {
  messages: KbChatSessionMessage[];
}

export const kbChatApi = {
  invoke: (request: KbChatRequest) =>
    apiClient.post<KbChatResponse>("/api/v1/kb-chat/invoke", request),

  stream: (request: KbChatRequest) =>
    apiClient.postStream("/api/v1/kb-chat/stream", request),

  listSessions: (limit: number = 30) =>
    apiClient.get<KbChatSessionSummary[]>(`/api/v1/kb-chat/sessions?limit=${limit}`),

  getSession: (sessionId: string) =>
    apiClient.get<KbChatSessionDetail>(
      `/api/v1/kb-chat/sessions/${encodeURIComponent(sessionId)}`,
    ),
};
