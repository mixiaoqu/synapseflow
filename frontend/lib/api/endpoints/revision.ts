import { apiClient } from "../client";

export interface RevisionRequest {
  document: string;
  suggestions?: string;
  doc_id?: number | null;
  max_iterations?: number;
}

export interface RevisionResponse {
  revised_document: string;
  revision_history?: any[];
  confidence?: number;
  iterations?: number;
}

export const revisionApi = {
  invoke: (request: RevisionRequest) =>
    apiClient.post<RevisionResponse>("/api/v1/revision/suggest", request),

  stream: (request: RevisionRequest) =>
    apiClient.postStream("/api/v1/revision/stream", request),
};
