import { apiClient } from "../client";

export interface KbChatRequest {
  query: string;
  knowledge_base_id?: number | null;
}

export interface RetrievedDoc {
  content: string;
  metadata?: {
    document_id?: number;
    document_title?: string;
    chunk_index?: number;
    score?: number;
    rerank_score?: number;
  };
}

export interface KbChatResponse {
  answer: string;
  retrieved_docs: RetrievedDoc[];
}

export const kbChatApi = {
  invoke: (request: KbChatRequest) =>
    apiClient.post<KbChatResponse>("/api/v1/kb-chat/invoke", request),

  stream: (request: KbChatRequest) =>
    apiClient.postStream("/api/v1/kb-chat/stream", request),
};
