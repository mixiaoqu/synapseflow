import { apiClient } from "../client";

export interface QARequest {
  query: string;
  max_iterations?: number;
  session_id?: string;
}

export interface QAResponse {
  answer: string;
  confidence_score: number;
  iteration: number;
  retrieved_docs: any[];
  session_id?: string;
}

export const qaApi = {
  invoke: (request: QARequest) =>
    apiClient.post<QAResponse>("/api/v1/qa/invoke", request),

  stream: (request: QARequest) =>
    apiClient.postStream("/api/v1/qa/stream", request),
};
