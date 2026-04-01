import { apiClient } from "../client";
import type { RetrievedDoc } from "./kbChat";

export interface KbCurationRequest {
  query: string;
  max_iterations?: number;
  knowledge_base_id?: number | null;
}

export interface IterationRecord {
  round: number;
  question: string;
  original_question?: string;
  answer: string;
  score: number;
  passed: boolean;
  reason?: string;
  suggestion?: string;
}

export interface DocumentIssue {
  round?: number;
  type?: string;
  document_title?: string;
  description?: string;
  modification_suggestion?: string;
}

export interface KbCurationResponse {
  answer: string;
  confidence_score: number;
  iteration: number;
  retrieved_docs: RetrievedDoc[];
  iteration_history: IterationRecord[];
  document_issues?: DocumentIssue[];
}

export const kbCurationApi = {
  invoke: (request: KbCurationRequest) =>
    apiClient.post<KbCurationResponse>("/api/v1/kb-curation/invoke", request),

  stream: (request: KbCurationRequest) =>
    apiClient.postStream("/api/v1/kb-curation/stream", request),
};
