import { request } from "@/shared/api/http";

import type {
  ListQaLogsParams,
  QaLogDetail,
  QaLogDetailResponse,
  QaLogListResponse,
  QaLogSummary,
} from "@/modules/qa-logs/types";

function mapQaLog(item: QaLogListResponse["items"][number]): QaLogSummary {
  return {
    id: item.id,
    userId: item.user_id,
    sessionId: item.session_id,
    productId: item.product_id,
    projectId: item.project_id,
    projectName: item.project_name,
    projectAppId: item.project_app_id,
    projectAppName: item.project_app_name,
    externalUserId: item.external_user_id,
    externalUserName: item.external_user_name,
    teamId: item.team_id,
    teamName: item.team_name,
    knowledgeBaseId: item.knowledge_base_id,
    knowledgeBaseName: item.knowledge_base_name,
    assistantId: item.assistant_id,
    assistantName: item.assistant_name,
    categoryId: item.category_id,
    categoryName: item.category_name,
    query: item.query,
    answerText: item.answer_text,
    answerStatus: item.answer_status,
    retrievalStatus: item.retrieval_status,
    latencyMs: item.latency_ms,
    textHitCount: item.text_hit_count ?? 0,
    graphHitCount: item.graph_hit_count ?? 0,
    mergedCandidateCount: item.merged_candidate_count ?? 0,
    finalContextCount: item.final_context_count ?? 0,
    emptyReason: item.empty_reason ?? null,
    rerankEnabled: item.rerank_enabled ?? false,
    feedbackValue: item.feedback_value,
    feedbackNote: item.feedback_note,
    suggestedReviewLabel: item.suggested_review_label,
    reviewLabel: item.review_label,
    reviewNote: item.review_note,
    reviewedAt: item.reviewed_at,
    reviewedByUserId: item.reviewed_by_user_id,
    createdAt: item.created_at,
  };
}

function mapQaLogDetail(item: QaLogDetailResponse): QaLogDetail {
  return {
    ...mapQaLog(item),
    retrievalStatusReason: item.retrieval_status_reason,
    tracePayload: item.trace_payload,
    conversationContext: (item.conversation_context || []).map((message) => ({
      role: message.role,
      content: message.content,
      createdAt: message.created_at,
      isCurrentTurn: message.is_current_turn,
    })),
  };
}

export async function listQaLogs(params: ListQaLogsParams = {}) {
  const response = await request<QaLogListResponse>({
    url: "/admin/qa/logs",
    method: "GET",
    params,
  });

  return {
    total: response.total,
    page: response.page,
    pageSize: response.page_size,
    items: response.items.map(mapQaLog),
  };
}

export async function getQaLogDetail(logId: number) {
  const response = await request<QaLogDetailResponse>({
    url: `/admin/qa/logs/${logId}`,
    method: "GET",
  });

  return mapQaLogDetail(response);
}
