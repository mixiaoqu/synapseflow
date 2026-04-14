import { apiClient } from "../client";

export interface PrototypeRequest {
  requirements: string;
}

export interface PrototypeResponse {
  preview_url: string;
  html: string;
  is_valid: boolean;
  validation_errors: string[];
  metadata: Record<string, any>;
}

export const prototypeApi = {
  generate: (request: PrototypeRequest) =>
    apiClient.post<PrototypeResponse>("/api/v1/prototype/generate", request),

  generateStream: (request: PrototypeRequest) =>
    apiClient.postStream("/api/v1/prototype/generate/stream", request),
};
