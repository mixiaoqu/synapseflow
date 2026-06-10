export interface ContentRiskLibrarySummary {
  id: number;
  name: string;
  description: string | null;
  enabled: boolean;
  ruleCount: number;
  referenceCount: number;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface ContentRiskLibraryListResponse {
  items: Array<{
    id: number;
    name: string;
    description: string | null;
    enabled: boolean;
    rule_count: number;
    reference_count: number;
    created_at: string | null;
    updated_at: string | null;
  }>;
}

export interface ListContentRiskLibrariesParams {
  keyword?: string;
  enabled?: boolean;
}

export interface ContentRiskLibraryUpsertPayload {
  name: string;
  description?: string | null;
  enabled: boolean;
}

export type ContentRiskRuleType = "keyword" | "regex";
export type ContentRiskMatchMode = "contains" | "exact" | "regex";
export type ContentRiskLevel = "low" | "medium" | "high";
export type ContentRiskAction = "block" | "review" | "log";
export type ContentRiskScene = "query" | "answer";
export type ContentRiskResolvedAction = "pass" | ContentRiskAction;

export interface ContentRiskRuleSummary {
  id: number;
  libraryId: number;
  name: string;
  description: string | null;
  ruleType: ContentRiskRuleType;
  matchMode: ContentRiskMatchMode;
  pattern: string;
  riskCategory: string;
  riskLevel: ContentRiskLevel;
  defaultAction: ContentRiskAction;
  appliesToQuery: boolean;
  appliesToAnswer: boolean;
  enabled: boolean;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface ContentRiskRuleListResponse {
  items: Array<{
    id: number;
    library_id: number;
    name: string;
    description: string | null;
    rule_type: ContentRiskRuleType;
    match_mode: ContentRiskMatchMode;
    pattern: string;
    risk_category: string;
    risk_level: ContentRiskLevel;
    default_action: ContentRiskAction;
    applies_to_query: boolean;
    applies_to_answer: boolean;
    enabled: boolean;
    created_at: string | null;
    updated_at: string | null;
  }>;
  total: number;
  page: number;
  page_size: number;
}

export interface ListContentRiskRulesParams {
  keyword?: string;
  enabled?: boolean;
  scene?: ContentRiskScene;
  page?: number;
  page_size?: number;
}

export interface ContentRiskRuleUpsertPayload {
  name: string;
  description?: string | null;
  rule_type: ContentRiskRuleType;
  match_mode: ContentRiskMatchMode;
  pattern: string;
  risk_category: string;
  risk_level: ContentRiskLevel;
  default_action: ContentRiskAction;
  applies_to_query: boolean;
  applies_to_answer: boolean;
  enabled: boolean;
}

export interface ContentRiskTestPayload {
  scene: ContentRiskScene;
  text: string;
}

export interface ContentRiskTestResponse {
  scene: ContentRiskScene;
  action: ContentRiskResolvedAction;
  blocked: boolean;
  risk_level: ContentRiskLevel | null;
  elapsed_ms: number;
  hits: Array<{
    rule_id: number;
    library_id: number;
    rule_name: string;
    risk_category: string;
    risk_level: ContentRiskLevel;
    action: ContentRiskAction;
    match_mode: ContentRiskMatchMode;
    pattern: string;
    matched_text: string;
  }>;
}

export interface ContentRiskTestResult {
  scene: ContentRiskScene;
  action: ContentRiskResolvedAction;
  blocked: boolean;
  riskLevel: ContentRiskLevel | null;
  elapsedMs: number;
  hits: Array<{
    ruleId: number;
    libraryId: number;
    ruleName: string;
    riskCategory: string;
    riskLevel: ContentRiskLevel;
    action: ContentRiskAction;
    matchMode: ContentRiskMatchMode;
    pattern: string;
    matchedText: string;
  }>;
}

export interface ListContentRiskLogsParams {
  page?: number;
  page_size?: number;
  team_id?: number;
  scene?: ContentRiskScene;
  action?: ContentRiskResolvedAction;
  blocked?: boolean;
  risk_level?: ContentRiskLevel;
  chat_log_id?: number;
}

export interface ContentRiskLogListResponse {
  total: number;
  items: Array<{
    id: number;
    chat_log_id: number | null;
    user_id: number | null;
    session_id: string | null;
    product_id: number | null;
    product_name: string | null;
  project_id: number | null;
  project_name: string | null;
  project_app_id: number | null;
  project_app_name: string | null;
  team_id: number | null;
  team_name: string | null;
  external_user_id: string | null;
    external_user_name: string | null;
    knowledge_base_id: number | null;
    knowledge_base_name: string | null;
    assistant_id: number | null;
    assistant_name: string | null;
    scene: ContentRiskScene;
    action: ContentRiskResolvedAction;
    blocked: boolean;
    risk_level: ContentRiskLevel | null;
    matched_text: string | null;
    checked_text: string;
    hits: ContentRiskTestResponse["hits"];
    elapsed_ms: number;
    created_at: string | null;
  }>;
}

export interface ContentRiskLogSummary {
  id: number;
  chatLogId: number | null;
  userId: number | null;
  sessionId: string | null;
  productId: number | null;
  productName: string | null;
  projectId: number | null;
  projectName: string | null;
  projectAppId: number | null;
  projectAppName: string | null;
  teamId: number | null;
  teamName: string | null;
  externalUserId: string | null;
  externalUserName: string | null;
  knowledgeBaseId: number | null;
  knowledgeBaseName: string | null;
  assistantId: number | null;
  assistantName: string | null;
  scene: ContentRiskScene;
  action: ContentRiskResolvedAction;
  blocked: boolean;
  riskLevel: ContentRiskLevel | null;
  matchedText: string | null;
  checkedText: string;
  hits: ContentRiskTestResult["hits"];
  elapsedMs: number;
  createdAt: string | null;
}
