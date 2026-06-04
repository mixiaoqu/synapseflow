import { request } from "@/shared/api/http";

import type {
  ContentRiskLibraryListResponse,
  ContentRiskLibrarySummary,
  ContentRiskLibraryUpsertPayload,
  ContentRiskLogListResponse,
  ContentRiskLogSummary,
  ContentRiskRuleListResponse,
  ContentRiskRuleSummary,
  ContentRiskRuleUpsertPayload,
  ContentRiskTestPayload,
  ContentRiskTestResponse,
  ContentRiskTestResult,
  ListContentRiskLibrariesParams,
  ListContentRiskLogsParams,
  ListContentRiskRulesParams,
} from "@/modules/content-risk/types";

function mapLibrary(item: ContentRiskLibraryListResponse["items"][number]): ContentRiskLibrarySummary {
  return {
    id: item.id,
    name: item.name,
    description: item.description,
    enabled: item.enabled,
    ruleCount: item.rule_count,
    referenceCount: item.reference_count,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

function mapRule(item: ContentRiskRuleListResponse["items"][number]): ContentRiskRuleSummary {
  return {
    id: item.id,
    libraryId: item.library_id,
    name: item.name,
    description: item.description,
    ruleType: item.rule_type,
    matchMode: item.match_mode,
    pattern: item.pattern,
    riskCategory: item.risk_category,
    riskLevel: item.risk_level,
    defaultAction: item.default_action,
    appliesToQuery: item.applies_to_query,
    appliesToAnswer: item.applies_to_answer,
    enabled: item.enabled,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

function mapTestResult(response: ContentRiskTestResponse): ContentRiskTestResult {
  return {
    scene: response.scene,
    action: response.action,
    blocked: response.blocked,
    riskLevel: response.risk_level,
    elapsedMs: response.elapsed_ms,
    hits: response.hits.map((hit) => ({
      ruleId: hit.rule_id,
      libraryId: hit.library_id,
      ruleName: hit.rule_name,
      riskCategory: hit.risk_category,
      riskLevel: hit.risk_level,
      action: hit.action,
      matchMode: hit.match_mode,
      pattern: hit.pattern,
      matchedText: hit.matched_text,
    })),
  };
}

function mapLog(item: ContentRiskLogListResponse["items"][number]): ContentRiskLogSummary {
  return {
    id: item.id,
    chatLogId: item.chat_log_id,
    userId: item.user_id,
    sessionId: item.session_id,
    productId: item.product_id,
    productName: item.product_name,
    projectId: item.project_id,
    projectName: item.project_name,
    projectAppId: item.project_app_id,
    projectAppName: item.project_app_name,
    externalUserId: item.external_user_id,
    externalUserName: item.external_user_name,
    knowledgeBaseId: item.knowledge_base_id,
    knowledgeBaseName: item.knowledge_base_name,
    assistantId: item.assistant_id,
    assistantName: item.assistant_name,
    scene: item.scene,
    action: item.action,
    blocked: item.blocked,
    riskLevel: item.risk_level,
    matchedText: item.matched_text,
    checkedText: item.checked_text,
    hits: item.hits.map((hit) => ({
      ruleId: hit.rule_id,
      libraryId: hit.library_id,
      ruleName: hit.rule_name,
      riskCategory: hit.risk_category,
      riskLevel: hit.risk_level,
      action: hit.action,
      matchMode: hit.match_mode,
      pattern: hit.pattern,
      matchedText: hit.matched_text,
    })),
    elapsedMs: item.elapsed_ms,
    createdAt: item.created_at,
  };
}

export async function listContentRiskLibraries(params: ListContentRiskLibrariesParams = {}) {
  const response = await request<ContentRiskLibraryListResponse>({
    url: "/content-risk/libraries",
    method: "GET",
    params,
  });

  return response.items.map(mapLibrary);
}

export async function createContentRiskLibrary(payload: ContentRiskLibraryUpsertPayload) {
  const response = await request<ContentRiskLibraryListResponse["items"][number], ContentRiskLibraryUpsertPayload>({
    url: "/content-risk/libraries",
    method: "POST",
    data: payload,
  });

  return mapLibrary(response);
}

export async function updateContentRiskLibrary(
  libraryId: number,
  payload: ContentRiskLibraryUpsertPayload,
) {
  const response = await request<ContentRiskLibraryListResponse["items"][number], ContentRiskLibraryUpsertPayload>({
    url: `/content-risk/libraries/${libraryId}`,
    method: "PUT",
    data: payload,
  });

  return mapLibrary(response);
}

export async function listContentRiskRules(
  libraryId: number,
  params: ListContentRiskRulesParams = {},
) {
  const response = await request<ContentRiskRuleListResponse>({
    url: `/content-risk/libraries/${libraryId}/rules`,
    method: "GET",
    params,
  });

  return response.items.map(mapRule);
}

export async function createContentRiskRule(
  libraryId: number,
  payload: ContentRiskRuleUpsertPayload,
) {
  const response = await request<ContentRiskRuleListResponse["items"][number], ContentRiskRuleUpsertPayload>({
    url: `/content-risk/libraries/${libraryId}/rules`,
    method: "POST",
    data: payload,
  });

  return mapRule(response);
}

export async function updateContentRiskRule(
  libraryId: number,
  ruleId: number,
  payload: ContentRiskRuleUpsertPayload,
) {
  const response = await request<ContentRiskRuleListResponse["items"][number], ContentRiskRuleUpsertPayload>({
    url: `/content-risk/libraries/${libraryId}/rules/${ruleId}`,
    method: "PUT",
    data: payload,
  });

  return mapRule(response);
}

export async function testContentRiskText(payload: ContentRiskTestPayload) {
  const response = await request<ContentRiskTestResponse, ContentRiskTestPayload>({
    url: "/content-risk/test",
    method: "POST",
    data: payload,
  });

  return mapTestResult(response);
}

export async function listContentRiskLogs(params: ListContentRiskLogsParams = {}) {
  const response = await request<ContentRiskLogListResponse>({
    url: "/content-risk/logs",
    method: "GET",
    params,
  });

  return {
    total: response.total,
    items: response.items.map(mapLog),
  };
}
