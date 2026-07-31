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
  team_id?: number;
  project_id?: number;
  project_app_id?: number;
  external_user_id?: string;
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
    latency_ms: number | null;
    text_hit_count: number;
    graph_hit_count: number;
    merged_candidate_count: number;
    final_context_count: number;
    empty_reason: string | null;
    rerank_enabled: boolean;
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
  latencyMs: number | null;
  textHitCount: number;
  graphHitCount: number;
  mergedCandidateCount: number;
  finalContextCount: number;
  emptyReason: string | null;
  rerankEnabled: boolean;
  feedbackValue: QaLogFeedbackValue | null;
  feedbackNote: string | null;
  suggestedReviewLabel: string | null;
  reviewLabel: string | null;
  reviewNote: string | null;
  reviewedAt: string | null;
  reviewedByUserId: number | null;
  createdAt: string;
}

export interface QaLogDiagnosticDoc {
  rank: number;
  original_rank?: number;
  title?: string;
  section_path?: string;
  source_type?: "hybrid" | "lexical" | "graph" | "vector" | string;
  source_label?: string;
  score?: number | null;
  selected?: boolean;
  identity?: string;
  content: string;
  metadata: Record<string, unknown>;
}

export interface QaLogDiagnosticMessage {
  role: string;
  content: string;
  createdAt: string;
  isCurrentTurn: boolean;
}

export interface QaLogTraceSourceSummary {
  query_count: number;
  recall_count: number;
  candidate_count: number;
  status: string;
}

export interface QaLogTraceFunnel {
  recall_total: number;
  duplicates_folded: number;
  merged_count: number;
  rerank_count: number;
  final_context_count: number;
}

export interface QaLogTraceBranchSummary {
  query: string;
  chunk_count: number;
}

export interface QaLogTracePayload {
  knowledge_plan?: {
    attempt_count?: number;
    standalone_query?: string;
    business_objects?: string[];
    action?: string;
    parameters?: Record<string, unknown>;
    ambiguity?: {
      needs_clarification?: boolean;
      clarification_question?: string;
      candidates?: string[];
    };
    subtasks?: Array<{
      id?: string;
      goal?: string;
      semantic_queries?: string[];
      parameter_abstract_queries?: string[];
      lexical_terms?: string[];
      evidence_requirement?: string;
    }>;
    retrieval_attempts?: Array<Record<string, unknown>>;
    retrieval_feedback?: Record<string, unknown>;
  } | null;
  subtask_results?: Array<{
    id?: string;
    goal?: string;
    evidence_requirement?: string;
    covered?: boolean;
    evidence_refs?: string[];
    answerable?: boolean;
    supported_claims?: string[];
    top_score?: number | null;
    raw_hit_count?: number;
    empty_reason?: string | null;
    coverage_status?: "covered" | "partial" | "weak" | "missed";
    failure_reason?: string | null;
    coverage_reason?: string | null;
    discovered_terms?: string[];
    provider_error?: Record<string, unknown>;
  }>;
  query_clues?: {
    semantic_queries?: string[];
    lexical_terms?: string[];
    candidate_entities?: string[];
  } | null;
  source_summary?: {
    vector?: QaLogTraceSourceSummary;
    lexical?: QaLogTraceSourceSummary;
    graph?: QaLogTraceSourceSummary;
  } | null;
  funnel?: QaLogTraceFunnel | null;
  branch_summaries?: {
    vector?: QaLogTraceBranchSummary[];
    lexical?: QaLogTraceBranchSummary[];
    graph?: QaLogTraceBranchSummary[];
  } | null;
  ranked_candidates?: QaLogDiagnosticDoc[];
  final_context_docs?: QaLogDiagnosticDoc[];
  supporting_evidence_docs?: QaLogDiagnosticDoc[];
  metadata_evidence_docs?: QaLogDiagnosticDoc[];
  debug?: Record<string, unknown>;
}

export interface QaLogDetailResponse {
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
  latency_ms: number | null;
  text_hit_count: number;
  graph_hit_count: number;
  merged_candidate_count: number;
  final_context_count: number;
  empty_reason: string | null;
  rerank_enabled: boolean;
  feedback_value: QaLogFeedbackValue | null;
  feedback_note: string | null;
  suggested_review_label: string | null;
  review_label: string | null;
  review_note: string | null;
  reviewed_at: string | null;
  reviewed_by_user_id: number | null;
  created_at: string;
  retrieval_status_reason: string | null;
  trace_payload: QaLogTracePayload | null;
  conversation_context: Array<{
    role: string;
    content: string;
    created_at: string;
    is_current_turn: boolean;
  }>;
}

export interface QaLogDetail extends QaLogSummary {
  retrievalStatusReason: string | null;
  tracePayload: QaLogTracePayload | null;
  conversationContext: QaLogDiagnosticMessage[];
}
