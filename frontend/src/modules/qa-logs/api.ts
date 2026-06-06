import { request } from "@/shared/api/http";

import type {
  ListQaLogsParams,
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
    retrievedCount: item.retrieved_count,
    latencyMs: item.latency_ms,
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
