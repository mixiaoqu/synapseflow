export interface AssistantSummary {
  id: number;
  name: string;
  slug: string;
  team_id: number;
  team_name: string | null;
  created_by_user_id: number | null;
  created_by_name: string | null;
  description: string | null;
  welcome_message: string | null;
  placeholder_text: string | null;
  llm_model_key: string | null;
  suggested_prompts: string[];
  is_active: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface AssistantDetail extends AssistantSummary {
  persona_prompt: string | null;
  rule_template: string | null;
}

export interface AssistantModelOption {
  key: string;
  name: string;
  provider: string;
  model: string;
}

export interface AssistantDependencyUsage {
  assistant_id: number;
  active_session_count: number;
  related_log_count: number;
  has_dependencies: boolean;
}

export interface AssistantPreviewResponse {
  answer: string;
  answer_text: string;
  answer_status: string;
  backend_citations: Array<Record<string, unknown>>;
  retrieved_docs: Array<Record<string, unknown>>;
  assistant_id?: number | null;
  assistant_name?: string | null;
  session_id?: string | null;
  log_id?: number | null;
}

export interface AssistantUpsertPayload {
  name: string;
  slug: string;
  current_team_id: number;
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

export interface AssistantPreviewPayload extends Omit<AssistantUpsertPayload, "name"> {
  query: string;
  name?: string | null;
  include_unpublished?: boolean;
}

export type AssistantBulkAction = "enable" | "disable" | "delete";

export interface AssistantBulkActionResponse {
  action: AssistantBulkAction;
  affected_ids: number[];
  affected_count: number;
}
