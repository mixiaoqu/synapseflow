import { apiClient } from "../client";
import type {
  AskResponse,
  AskSessionDetail,
  AskSessionSummary,
} from "./ask";

export interface EmbedAssistantBootstrap {
  project_id: number;
  project_code: string;
  project_name: string;
  project_app_id: number;
  app_code: string;
  app_name: string;
  assistant_id: number;
  assistant_name: string;
  welcome_message?: string | null;
  placeholder_text?: string | null;
  suggested_prompts: string[];
}

function embedAuthHeaders(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
  };
}

export const embedApi = {
  bootstrap: (token: string) =>
    apiClient.get<EmbedAssistantBootstrap>("/api/v1/embed/assistant/bootstrap", {
      auth: false,
      headers: embedAuthHeaders(token),
    }),

  listSessions: (token: string, limit: number = 30) =>
    apiClient.get<AskSessionSummary[]>(
      `/api/v1/embed/assistant/sessions?limit=${limit}`,
      {
        auth: false,
        headers: embedAuthHeaders(token),
      },
    ),

  getSession: (token: string, sessionId: string) =>
    apiClient.get<AskSessionDetail>(
      `/api/v1/embed/assistant/sessions/${encodeURIComponent(sessionId)}`,
      {
        auth: false,
        headers: embedAuthHeaders(token),
      },
    ),

  deleteSession: (token: string, sessionId: string) =>
    apiClient.delete<void>(
      `/api/v1/embed/assistant/sessions/${encodeURIComponent(sessionId)}`,
      {
        auth: false,
        headers: embedAuthHeaders(token),
      },
    ),

  invoke: (
    token: string,
    payload: { query: string; session_id?: string | null },
  ) =>
    apiClient.post<AskResponse>("/api/v1/embed/assistant/invoke", payload, {
      auth: false,
      headers: embedAuthHeaders(token),
    }),

  stream: (
    token: string,
    payload: { query: string; session_id?: string | null },
    signal?: AbortSignal,
  ) =>
    apiClient.postStream("/api/v1/embed/assistant/stream", payload, {
      auth: false,
      headers: embedAuthHeaders(token),
      signal,
    }),

  submitFeedback: (
    token: string,
    logId: number,
    payload: { feedback_value: string; feedback_note?: string | null },
  ) =>
    apiClient.post(`/api/v1/embed/assistant/feedback/${logId}`, payload, {
      auth: false,
      headers: embedAuthHeaders(token),
    }),
};
