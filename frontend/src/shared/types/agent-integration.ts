export interface McpServer {
  id: number;
  team_id: number;
  team_name?: string | null;
  name: string;
  description?: string | null;
  environment: string;
  endpoint_url: string;
  transport_type: string;
  auth_type: string;
  auth_header_name?: string | null;
  has_auth_token: boolean;
  auth_token_masked?: string | null;
  enabled: boolean;
  status: string;
  last_checked_at?: string | null;
  last_error?: string | null;
  tool_count: number;
  created_at: string;
  updated_at: string;
}

export interface McpServerPayload {
  team_id: number;
  name: string;
  description?: string | null;
  environment: string;
  endpoint_url: string;
  transport_type: string;
  auth_type: string;
  auth_token?: string | null;
  auth_header_name?: string | null;
  enabled: boolean;
}

export interface McpServerListResponse {
  items: McpServer[];
  total: number;
  page: number;
  page_size: number;
}

export interface McpServerTestResponse {
  success: boolean;
  status: string;
  message: string;
  duration_ms?: number | null;
  tool_count: number;
}

export interface McpTool {
  id: number;
  mcp_server_id: number;
  server_name?: string | null;
  raw_name: string;
  raw_description?: string | null;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  schema_hash: string;
  sync_status: string;
  raw_payload: Record<string, unknown>;
  last_synced_at?: string | null;
  agent_tool_id?: number | null;
  agent_tool_status?: string | null;
  agent_tool_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface McpToolListResponse {
  items: McpTool[];
  total: number;
  page: number;
  page_size: number;
}

export interface McpToolSyncResponse {
  server_id: number;
  synced_count: number;
  message: string;
}

export interface AgentTool {
  id: number;
  team_id: number;
  team_name?: string | null;
  mcp_tool_id: number;
  mcp_server_id?: number | null;
  mcp_server_name?: string | null;
  mcp_tool_name?: string | null;
  tool_key: string;
  name: string;
  description?: string | null;
  agent_description?: string | null;
  params_schema: Record<string, unknown>;
  response_schema: Record<string, unknown>;
  tool_type: string;
  risk_level: string;
  requires_confirmation: boolean;
  enabled: boolean;
  status: string;
  last_tested_at?: string | null;
  last_test_error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentToolPayload {
  team_id: number;
  mcp_tool_id: number;
  tool_key: string;
  name: string;
  description?: string | null;
  agent_description?: string | null;
  params_schema: Record<string, unknown>;
  response_schema: Record<string, unknown>;
  risk_level: string;
  requires_confirmation: boolean;
  enabled: boolean;
}

export interface AgentToolListResponse {
  items: AgentTool[];
  total: number;
  page: number;
  page_size: number;
}

export interface AgentToolTestResponse {
  success: boolean;
  status: string;
  message: string;
  duration_ms?: number | null;
  data: Record<string, unknown>;
  error_message?: string | null;
}

export interface AgentToolPublishResponse {
  id: number;
  status: string;
  message: string;
}

export interface AgentAppToolSetBinding {
  id: number;
  project_app_id: number;
  mcp_server_id: number;
  mcp_server_name: string;
  mcp_server_description?: string | null;
  tool_count: number;
  enabled: boolean;
  unavailable_reason?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentAppToolSetBindingPayload {
  mcp_server_id: number;
  enabled: boolean;
}

export interface AgentAppToolSetBindingListResponse {
  items: AgentAppToolSetBinding[];
}

export interface AgentToolCallLog {
  id: number;
  team_id: number;
  team_name?: string | null;
  project_app_id?: number | null;
  project_app_name?: string | null;
  agent_tool_id?: number | null;
  mcp_server_id?: number | null;
  mcp_server_name?: string | null;
  session_id?: string | null;
  trace_id?: string | null;
  actor_user_id?: number | null;
  external_user_id?: string | null;
  tool_key: string;
  mcp_tool_name: string;
  status: string;
  duration_ms?: number | null;
  request_payload: Record<string, unknown>;
  response_payload: Record<string, unknown>;
  error_message?: string | null;
  confirmed: boolean;
  confirmed_at?: string | null;
  created_at: string;
}

export interface AgentToolCallLogListResponse {
  items: AgentToolCallLog[];
  total: number;
  page: number;
  page_size: number;
}
