export type QaLogAnswerStatus = "answered" | "partial" | "insufficient" | "blocked" | string;
export type QaLogRetrievalStatus =
  | "ok"
  | "no_hits"
  | "empty_collection"
  | "empty_knowledge_base"
  | string;
export type QaLogFeedbackValue = "helpful" | "not_helpful" | string;

export interface ListQaLogsParams {
  page?: number;
  page_size?: number;
  answer_status?: string;
  retrieval_status?: string;
  feedback_value?: string;
  query_keyword?: string;
  zero_hits_only?: boolean;
  high_latency_only?: boolean;
  high_latency_threshold_ms?: number;
}

export interface QaLogListResponse {
  total: number;
  page: number;
  page_size: number;
  items: Array<{
    id: number;
    user_id: number | null;
    session_id: string | null;
    product_id: number | null;
    project_id: number | null;
    project_name: string | null;
    project_app_id: number | null;
    project_app_name: string | null;
    external_user_id: string | null;
    external_user_name: string | null;
    team_id: number | null;
    team_name: string | null;
    knowledge_base_id: number | null;
    knowledge_base_name: string | null;
    assistant_id: number | null;
    assistant_name: string | null;
    category_id: number | null;
    category_name: string | null;
    query: string;
    answer_text: string;
    answer_status: QaLogAnswerStatus;
    retrieval_status: QaLogRetrievalStatus | null;
    retrieved_count: number;
    latency_ms: number | null;
    feedback_value: QaLogFeedbackValue | null;
    feedback_note: string | null;
    suggested_review_label: string | null;
    review_label: string | null;
    review_note: string | null;
    reviewed_at: string | null;
    reviewed_by_user_id: number | null;
    created_at: string;
  }>;
}

export interface QaLogSummary {
  id: number;
  userId: number | null;
  sessionId: string | null;
  productId: number | null;
  projectId: number | null;
  projectName: string | null;
  projectAppId: number | null;
  projectAppName: string | null;
  externalUserId: string | null;
  externalUserName: string | null;
  teamId: number | null;
  teamName: string | null;
  knowledgeBaseId: number | null;
  knowledgeBaseName: string | null;
  assistantId: number | null;
  assistantName: string | null;
  categoryId: number | null;
  categoryName: string | null;
  query: string;
  answerText: string;
  answerStatus: QaLogAnswerStatus;
  retrievalStatus: QaLogRetrievalStatus | null;
  retrievedCount: number;
  latencyMs: number | null;
  feedbackValue: QaLogFeedbackValue | null;
  feedbackNote: string | null;
  suggestedReviewLabel: string | null;
  reviewLabel: string | null;
  reviewNote: string | null;
  reviewedAt: string | null;
  reviewedByUserId: number | null;
  createdAt: string;
}
