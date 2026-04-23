import { apiClient } from "../client";

export interface AskRequest {
  query: string;
  team_id?: number | null;
  project_id?: number | null;
  project_app_id?: number | null;
  external_user_id?: string | null;
  knowledge_base_id?: number | null;
  category_id?: number | null;
  session_id?: string | null;
}

export interface AskTeamOption {
  id: number;
  name: string;
  code?: string | null;
  description?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AskRetrievedDoc {
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

export interface AskResponse {
  answer: string;
  answer_text: string;
  answer_status: string;
  confidence_level?: string | null;
  backend_citations: AskRetrievedDoc[];
  retrieved_docs: AskRetrievedDoc[];
  assistant_id?: number | null;
  assistant_name?: string | null;
  session_id?: string | null;
  log_id?: number | null;
}

export interface AskSessionMessage {
  role: string;
  content: string;
  retrieved_docs?: AskRetrievedDoc[];
  answer_status?: string | null;
  log_id?: number | null;
  created_at: string;
}

export interface AskSessionSummary {
  session_id: string;
  title: string;
  preview?: string | null;
  project_id?: number | null;
  project_app_id?: number | null;
  external_user_id?: string | null;
  external_user_name?: string | null;
  source?: string | null;
  team_id?: number | null;
  knowledge_base_id?: number | null;
  knowledge_base_name?: string | null;
  assistant_id?: number | null;
  assistant_name?: string | null;
  category_id?: number | null;
  category_name?: string | null;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface AskSessionDetail extends AskSessionSummary {
  messages: AskSessionMessage[];
}

export interface AskLogItem {
  id: number;
  user_id: number | null;
  session_id?: string | null;
  project_id?: number | null;
  project_name?: string | null;
  project_app_id?: number | null;
  project_app_name?: string | null;
  external_user_id?: string | null;
  external_user_name?: string | null;
  source?: string | null;
  team_id?: number | null;
  team_name?: string | null;
  knowledge_base_id?: number | null;
  knowledge_base_name?: string | null;
  assistant_id?: number | null;
  assistant_name?: string | null;
  category_id?: number | null;
  category_name?: string | null;
  query: string;
  answer_text: string;
  answer_status: string;
  retrieval_status?: string | null;
  retrieved_count: number;
  latency_ms?: number | null;
  feedback_value?: string | null;
  feedback_note?: string | null;
  suggested_review_label?: string | null;
  review_label?: string | null;
  review_note?: string | null;
  reviewed_at?: string | null;
  reviewed_by_user_id?: number | null;
  created_at: string;
}

export interface AskDiagnosticDoc {
  rank: number;
  content: string;
  metadata: {
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

export interface AskDiagnosticMessage {
  role: string;
  content: string;
  created_at: string;
  is_current_turn: boolean;
}

export interface AskRetrievalQueryStat {
  query: string;
  chunk_count: number;
}

export interface AskRetrievalFunnelStage {
  key: string;
  label: string;
  chunk_count: number;
  note?: string | null;
}

export interface AskRetrievalFunnel {
  mode?: string | null;
  query_count: number;
  rewritten_queries: AskRetrievalQueryStat[];
  stages: AskRetrievalFunnelStage[];
}

export interface AskLogDetail extends AskLogItem {
  team_id?: number | null;
  team_name?: string | null;
  assistant_id?: number | null;
  assistant_name?: string | null;
  category_name?: string | null;
  retrieval_status_reason?: string | null;
  retrieval_queries: string[];
  retrieval_funnel?: AskRetrievalFunnel | null;
  answer_context?: string | null;
  retrieved_docs: AskDiagnosticDoc[];
  conversation_context: AskDiagnosticMessage[];
}

export interface AskLogListResponse {
  items: AskLogItem[];
  total: number;
}

export interface AskLogListFilters {
  project_id?: number | null;
  project_app_id?: number | null;
  external_user_id?: string | null;
  limit?: number;
  team_id?: number | null;
  knowledge_base_id?: number | null;
  category_id?: number | null;
  answer_status?: string | null;
  retrieval_status?: string | null;
  feedback_value?: string | null;
  query_keyword?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  zero_hits_only?: boolean;
  high_latency_only?: boolean;
  high_latency_threshold_ms?: number;
}

export const askApi = {
  invoke: (request: AskRequest) =>
    apiClient.post<AskResponse>("/api/v1/ask/invoke", request),

  stream: (request: AskRequest) =>
    apiClient.postStream("/api/v1/ask/stream", request),

  listSessions: (limit: number = 30) =>
    apiClient.get<AskSessionSummary[]>(`/api/v1/ask/sessions?limit=${limit}`),

  listTeams: () => apiClient.get<AskTeamOption[]>("/api/v1/ask/teams"),

  getSession: (sessionId: string) =>
    apiClient.get<AskSessionDetail>(
      `/api/v1/ask/sessions/${encodeURIComponent(sessionId)}`,
    ),

  deleteSession: (sessionId: string) =>
    apiClient.delete<void>(`/api/v1/ask/sessions/${encodeURIComponent(sessionId)}`),

  submitFeedback: (
    logId: number,
    payload: { feedback_value: string; feedback_note?: string | null },
  ) => apiClient.post(`/api/v1/ask/feedback/${logId}`, payload),

  reviewLog: (
    logId: number,
    payload: { review_label?: string | null; review_note?: string | null },
  ) => apiClient.post(`/api/v1/admin/qa/logs/${logId}/review`, payload),

  preview: (request: AskRequest & { include_unpublished?: boolean }) =>
    apiClient.post<AskResponse>("/api/v1/admin/qa/preview", request),

  listLogs: (filters: AskLogListFilters = {}) => {
    const params = new URLSearchParams();
    params.set("limit", String(filters.limit ?? 50));
    if (filters.team_id != null) params.set("team_id", String(filters.team_id));
    if (filters.project_id != null) params.set("project_id", String(filters.project_id));
    if (filters.project_app_id != null) params.set("project_app_id", String(filters.project_app_id));
    if (filters.external_user_id) params.set("external_user_id", filters.external_user_id);
    if (filters.knowledge_base_id != null) {
      params.set("knowledge_base_id", String(filters.knowledge_base_id));
    }
    if (filters.category_id != null) params.set("category_id", String(filters.category_id));
    if (filters.answer_status) params.set("answer_status", filters.answer_status);
    if (filters.retrieval_status) params.set("retrieval_status", filters.retrieval_status);
    if (filters.feedback_value) params.set("feedback_value", filters.feedback_value);
    if (filters.query_keyword) params.set("query_keyword", filters.query_keyword);
    if (filters.start_date) params.set("start_date", filters.start_date);
    if (filters.end_date) params.set("end_date", filters.end_date);
    if (filters.zero_hits_only) params.set("zero_hits_only", "true");
    if (filters.high_latency_only) params.set("high_latency_only", "true");
    if (filters.high_latency_threshold_ms != null) {
      params.set("high_latency_threshold_ms", String(filters.high_latency_threshold_ms));
    }
    return apiClient.get<AskLogListResponse>(`/api/v1/admin/qa/logs?${params.toString()}`);
  },

  getLogDetail: (logId: number) =>
    apiClient.get<AskLogDetail>(`/api/v1/admin/qa/logs/${logId}`),
};
