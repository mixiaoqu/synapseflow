export type BusinessToolMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
export type BusinessToolRiskLevel = "low" | "medium" | "high";
export type BusinessToolStatus = "draft" | "verified" | "published" | "error";
export type BusinessConnectionEnvironment = "development" | "staging" | "production";
export type BusinessConnectionAuthType = "none" | "bearer" | "header";
export type BusinessConnectionStatus = "untested" | "available" | "error";
export type BusinessToolParamType = "text" | "number" | "boolean" | "array" | "object";
export type BusinessApiSourceType = "manual" | "openapi_imported";
export type BusinessToolImplementationType = "http";
export type BusinessApiFieldType = "string" | "number" | "boolean" | "array" | "object";
export type BusinessApiRequestFieldLocation = "query" | "path" | "header" | "body";

export interface BusinessConnection {
  id: number;
  team_id: number;
  team_name: string | null;
  name: string;
  description: string | null;
  environment: BusinessConnectionEnvironment;
  base_url: string;
  auth_type: BusinessConnectionAuthType;
  auth_secret_ref: string | null;
  auth_header_name: string | null;
  enabled: boolean;
  status: BusinessConnectionStatus;
  last_tested_at: string | null;
  last_test_error: string | null;
  tool_count: number;
  api_count: number;
  created_at: string;
  updated_at: string;
}

export interface BusinessConnectionPayload {
  team_id: number;
  name: string;
  description?: string | null;
  environment: BusinessConnectionEnvironment;
  base_url: string;
  auth_type: BusinessConnectionAuthType;
  auth_secret_ref?: string | null;
  auth_header_name?: string | null;
  enabled: boolean;
}

export interface BusinessConnectionListResponse {
  items: BusinessConnection[];
  total: number;
  page: number;
  page_size: number;
}

export interface BusinessConnectionTestResponse {
  success: boolean;
  status: BusinessConnectionStatus;
  http_status: number | null;
  duration_ms: number | null;
  message: string;
}

export interface BusinessToolParamSpec {
  key: string;
  label: string;
  type: BusinessToolParamType;
  required: boolean;
  description: string;
}

export interface BusinessApiRequestFieldSpec {
  name: string;
  label: string;
  in: BusinessApiRequestFieldLocation;
  type: BusinessApiFieldType;
  required: boolean;
  description: string;
}

export interface BusinessApiRequestSchema {
  fields: BusinessApiRequestFieldSpec[];
}

export interface BusinessApiResponseFieldSpec {
  path: string;
  label: string;
  type: BusinessApiFieldType;
  required: boolean;
  description: string;
}

export interface BusinessApiResponseSchema {
  fields: BusinessApiResponseFieldSpec[];
}

export interface BusinessApi {
  id: number;
  team_id: number;
  team_name: string | null;
  connection_id: number;
  connection_name: string;
  connection_environment: BusinessConnectionEnvironment;
  connection_status: BusinessConnectionStatus;
  api_key: string;
  name: string;
  description: string;
  method: BusinessToolMethod;
  path: string;
  request_schema: BusinessApiRequestSchema;
  response_schema: BusinessApiResponseSchema;
  source_type: BusinessApiSourceType;
  source_version: string | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface BusinessApiPayload {
  team_id: number;
  connection_id: number;
  api_key: string;
  name: string;
  description: string;
  method: BusinessToolMethod;
  path: string;
  request_schema: BusinessApiRequestSchema;
  response_schema: BusinessApiResponseSchema;
  source_type: BusinessApiSourceType;
  source_version?: string | null;
  enabled: boolean;
}

export interface BusinessApiListResponse {
  items: BusinessApi[];
  total: number;
  page: number;
  page_size: number;
}

export interface BusinessToolImplementationSummary {
  implementation_id: number;
  business_api_id: number;
  api_key: string;
  api_name: string;
  method: BusinessToolMethod;
  path: string;
  connection_id: number;
  connection_name: string;
  connection_environment: BusinessConnectionEnvironment;
  connection_status: BusinessConnectionStatus;
  implementation_status: BusinessToolStatus;
  enabled: boolean;
  priority: number;
}

export interface BusinessToolImplementation {
  id: number;
  business_tool_id: number;
  business_api_id: number;
  api_key: string;
  api_name: string;
  method: BusinessToolMethod;
  path: string;
  connection_id: number;
  connection_name: string;
  connection_environment: BusinessConnectionEnvironment;
  connection_status: BusinessConnectionStatus;
  implementation_type: BusinessToolImplementationType;
  context_binding: Record<string, unknown>;
  request_mapping: Record<string, unknown>;
  response_mapping: Record<string, unknown>;
  priority: number;
  enabled: boolean;
  status: BusinessToolStatus;
  last_tested_at: string | null;
  last_test_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface BusinessToolImplementationPayload {
  business_api_id: number;
  implementation_type: BusinessToolImplementationType;
  context_binding: Record<string, unknown>;
  request_mapping: Record<string, unknown>;
  response_mapping: Record<string, unknown>;
  priority: number;
  enabled: boolean;
}

export interface BusinessToolImplementationListResponse {
  items: BusinessToolImplementation[];
}

export interface BusinessTool {
  id: number;
  team_id: number;
  team_name: string | null;
  tool_key: string;
  name: string;
  description: string;
  typical_queries: string[];
  params_schema: BusinessToolParamSpec[];
  risk_level: BusinessToolRiskLevel;
  requires_confirmation: boolean;
  status: BusinessToolStatus;
  last_tested_at: string | null;
  last_test_error: string | null;
  enabled: boolean;
  implementation_count: number;
  primary_implementation: BusinessToolImplementationSummary | null;
  created_at: string;
  updated_at: string;
}

export interface BusinessToolListResponse {
  items: BusinessTool[];
  total: number;
  page: number;
  page_size: number;
}

export interface BusinessToolPayload {
  team_id: number;
  tool_key: string;
  name: string;
  description: string;
  typical_queries: string[];
  params_schema: BusinessToolParamSpec[];
  risk_level: BusinessToolRiskLevel;
  requires_confirmation: boolean;
  enabled: boolean;
}

export interface BusinessToolTestPayload {
  implementation_id?: number | null;
  scope: Record<string, unknown>;
  params: Record<string, unknown>;
}

export interface BusinessToolTestResponse {
  success: boolean;
  status: BusinessToolStatus;
  implementation_id: number | null;
  http_status: number | null;
  duration_ms: number | null;
  message: string;
  data: Record<string, unknown>;
  error_code: string | null;
}

export interface BusinessToolPublishResponse {
  id: number;
  status: BusinessToolStatus;
  published_implementation_ids: number[];
  message: string;
}

export interface BusinessToolCallLog {
  id: number;
  team_id: number;
  team_name: string | null;
  project_app_id: number | null;
  project_app_name: string | null;
  business_tool_id: number | null;
  business_api_id: number | null;
  business_tool_implementation_id: number | null;
  tool_key: string;
  tool_name: string;
  api_key: string | null;
  api_name: string | null;
  session_id: string | null;
  external_user_id: string | null;
  status: "success" | "error";
  http_status: number | null;
  duration_ms: number | null;
  request_payload: Record<string, unknown>;
  response_payload: Record<string, unknown>;
  error_message: string | null;
  created_at: string;
}

export interface BusinessToolCallLogListResponse {
  items: BusinessToolCallLog[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProjectAppBusinessToolBinding {
  id: number;
  project_app_id: number;
  business_tool_id: number;
  tool_key: string;
  name: string;
  description: string | null;
  risk_level: BusinessToolRiskLevel;
  status: BusinessToolStatus;
  enabled: boolean;
  tool_enabled: boolean;
  is_available: boolean;
  unavailable_reason: string | null;
  primary_implementation: BusinessToolImplementationSummary | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectAppBusinessToolBindingListResponse {
  items: ProjectAppBusinessToolBinding[];
}

export interface ProjectAppBusinessToolBindingPayload {
  business_tool_id: number;
  enabled: boolean;
}
