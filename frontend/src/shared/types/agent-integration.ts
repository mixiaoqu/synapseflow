export type ToolProviderTransport = "business_http" | "mcp_http";

export interface ToolProvider {
  id: number;
  team_id: number;
  team_name?: string | null;
  code: string;
  name: string;
  description?: string | null;
  base_url: string;
  transport_type: ToolProviderTransport;
  auth_type: "none" | "bearer" | "header";
  auth_header_name?: string | null;
  has_auth_token: boolean;
  auth_token_masked?: string | null;
  enabled: boolean;
  health_status: "untested" | "available" | "error";
  last_checked_at?: string | null;
  last_error?: string | null;
  tool_count: number;
  created_at: string;
  updated_at: string;
}

export interface ToolProviderPayload {
  team_id: number;
  code?: string;
  name: string;
  description?: string | null;
  base_url: string;
  transport_type: ToolProviderTransport;
  auth_type: "none" | "bearer" | "header";
  auth_header_name?: string | null;
  auth_token?: string | null;
  enabled: boolean;
}

export interface ToolProviderListResponse {
  items: ToolProvider[];
  total: number;
  page: number;
  page_size: number;
}

export interface ToolProviderTestResponse {
  success: boolean;
  health_status: string;
  message: string;
  duration_ms?: number | null;
  tool_count: number;
}

export interface AgentToolSyncResponse {
  provider_id: number;
  synced_count: number;
  message: string;
}

export interface AgentTool {
  id: number;
  provider_id: number;
  provider_code: string;
  provider_name: string;
  team_id: number;
  team_name?: string | null;
  external_name: string;
  external_description?: string | null;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  required_context: string[];
  schema_hash: string;
  sync_status: "active" | "removed" | "invalid";
  last_synced_at?: string | null;
  tool_key: string;
  name: string;
  agent_description?: string | null;
  risk_level: "low" | "medium" | "high";
  requires_confirmation: boolean;
  publish_status: "draft" | "published" | "needs_review";
  approved_schema_hash?: string | null;
  last_tested_at?: string | null;
  last_test_error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentToolUpdatePayload {
  name: string;
  agent_description?: string | null;
  risk_level: "low" | "medium" | "high";
  requires_confirmation: boolean;
}

export interface AgentToolListResponse {
  items: AgentTool[];
  total: number;
  page: number;
  page_size: number;
}

export interface AgentToolTestResponse {
  success: boolean;
  message: string;
  duration_ms?: number | null;
  data: Record<string, unknown>;
  error_code?: string | null;
}

export interface AgentToolPublishResponse {
  id: number;
  publish_status: string;
  message: string;
}

export interface AgentToolGrant {
  id: number;
  project_app_id: number;
  agent_tool_id: number;
  tool_key: string;
  tool_name: string;
  provider_id: number;
  provider_name: string;
  created_at: string;
}

export interface AgentToolGrantListResponse {
  items: AgentToolGrant[];
}

export interface AgentToolInvocation {
  id: number;
  team_id: number;
  team_name?: string | null;
  provider_id?: number | null;
  provider_name?: string | null;
  provider_code: string;
  project_app_id?: number | null;
  project_app_name?: string | null;
  agent_tool_id?: number | null;
  external_name: string;
  tool_key: string;
  schema_hash: string;
  session_id?: string | null;
  trace_id?: string | null;
  request_id?: string | null;
  actor_user_id?: number | null;
  external_user_id?: string | null;
  call_source: string;
  status: string;
  error_code?: string | null;
  error_message?: string | null;
  duration_ms?: number | null;
  request_summary: Record<string, unknown>;
  response_summary: Record<string, unknown>;
  confirmed: boolean;
  confirmed_at?: string | null;
  created_at: string;
}

export interface AgentToolInvocationListResponse {
  items: AgentToolInvocation[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProjectAppAccessCredential {
  project_app_id: number;
  client_id: string;
  client_secret_last_four: string;
  allowed_origins: string[];
  token_version: number;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectAppAccessIssuedCredential extends ProjectAppAccessCredential {
  client_secret: string;
}

export interface ProjectAppAccessCreatePayload {
  allowed_origins: string[];
}

export type ProjectAppAccessUpdatePayload = ProjectAppAccessCreatePayload;
