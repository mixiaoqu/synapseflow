import { apiClient } from "./client";
import type { AskResponse } from "./endpoints/ask";

export interface AssistantSummary {
  id: number;
  name: string;
  slug: string;
  team_id: number;
  team_name?: string | null;
  knowledge_base_id?: number | null;
  knowledge_base_name?: string | null;
  category_id?: number | null;
  category_name?: string | null;
  created_by_user_id?: number | null;
  created_by_name?: string | null;
  description?: string | null;
  welcome_message?: string | null;
  placeholder_text?: string | null;
  llm_model_key?: string | null;
  suggested_prompts: string[];
  is_active: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface AssistantProfile extends AssistantSummary {
  persona_prompt?: string | null;
  rule_template?: string | null;
}

export interface AssistantDependencyUsage {
  assistant_id: number;
  active_session_count: number;
  related_log_count: number;
  has_dependencies: boolean;
}

export interface AssistantAvailabilityResponse {
  items: AssistantSummary[];
}

export interface AssistantUpsertPayload {
  name: string;
  slug: string;
  current_team_id: number;
  knowledge_base_id?: number | null;
  category_id?: number | null;
  description?: string | null;
  welcome_message?: string | null;
  placeholder_text?: string | null;
  llm_model_key?: string | null;
  persona_prompt?: string | null;
  rule_template?: string | null;
  suggested_prompts: string[];
  is_active: boolean;
  sort_order: number;
}

export type AssistantBulkAction = "enable" | "disable" | "delete";

export interface AssistantBulkActionResponse {
  action: AssistantBulkAction;
  affected_ids: number[];
  affected_count: number;
}

export interface AssistantChatRequest {
  query: string;
  session_id?: string | null;
}

export interface AssistantPreviewRequest {
  query: string;
  name?: string | null;
  current_team_id: number;
  knowledge_base_id?: number | null;
  category_id?: number | null;
  welcome_message?: string | null;
  placeholder_text?: string | null;
  llm_model_key?: string | null;
  persona_prompt?: string | null;
  rule_template?: string | null;
  suggested_prompts?: string[];
  description?: string | null;
  is_active?: boolean;
  sort_order?: number;
  include_unpublished?: boolean;
}

export interface AssistantModelOption {
  key: string;
  name: string;
  provider: string;
  model: string;
}

export interface AssistantModelOptionsResponse {
  items: AssistantModelOption[];
}

export const assistantsApi = {
  list: (filters?: {
    team_id?: number | null;
    active_only?: boolean;
  }) => {
    const params = new URLSearchParams();
    if (filters?.team_id != null) params.set("team_id", String(filters.team_id));
    if (filters?.active_only) params.set("active_only", "true");
    return apiClient.get<AssistantSummary[]>(
      `/api/v1/assistants${params.size > 0 ? `?${params.toString()}` : ""}`,
    );
  },

  listAvailable: (filters?: {
    team_id?: number | null;
  }) => {
    const params = new URLSearchParams();
    if (filters?.team_id != null) params.set("team_id", String(filters.team_id));
    return apiClient.get<AssistantAvailabilityResponse>(
      `/api/v1/assistants/available${params.size > 0 ? `?${params.toString()}` : ""}`,
    );
  },

  get: (assistantId: number) =>
    apiClient.get<AssistantProfile>(`/api/v1/assistants/${assistantId}`),

  create: (payload: AssistantUpsertPayload) =>
    apiClient.post<AssistantProfile>("/api/v1/assistants", payload),

  reorder: (assistant_ids: number[]) =>
    apiClient.post<AssistantSummary[]>("/api/v1/assistants/reorder", { assistant_ids }),

  preview: (payload: AssistantPreviewRequest) =>
    apiClient.post<AskResponse>("/api/v1/assistants/preview", payload),

  listModelOptions: () =>
    apiClient.get<AssistantModelOptionsResponse>("/api/v1/assistants/model-options"),

  update: (assistantId: number, payload: AssistantUpsertPayload) =>
    apiClient.put<AssistantProfile>(`/api/v1/assistants/${assistantId}`, payload),

  bulkAction: (
    assistant_ids: number[],
    action: AssistantBulkAction,
    options?: { force?: boolean },
  ) =>
    apiClient.post<AssistantBulkActionResponse>("/api/v1/assistants/bulk-action", {
      assistant_ids,
      action,
      force: options?.force ?? false,
    }),

  getUsage: (assistantId: number) =>
    apiClient.get<AssistantDependencyUsage>(`/api/v1/assistants/${assistantId}/usage`),

  delete: (assistantId: number, options?: { force?: boolean }) =>
    apiClient.delete<{ message: string }>(
      `/api/v1/assistants/${assistantId}${options?.force ? "?force=true" : ""}`,
    ),

  invoke: (assistantId: number, payload: AssistantChatRequest) =>
    apiClient.post<AskResponse>(`/api/v1/assistants/${assistantId}/invoke`, payload),

  stream: (assistantId: number, payload: AssistantChatRequest) =>
    apiClient.postStream(`/api/v1/assistants/${assistantId}/stream`, payload),
};
