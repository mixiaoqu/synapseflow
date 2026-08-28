import type { KnowledgeBaseListResponse, KnowledgeBaseSummary } from "@/shared/types/knowledge-base";

export type EvalDatasetStatus = "draft" | "active" | "archived";
export type EvalRunStatus = "pending" | "running" | "completed" | "failed" | "canceled";
export type EvalCaseResultStatus = "pending" | "running" | "passed" | "failed";

export interface EvaluationKnowledgeBasePayload {
  name: string;
  team_id: number;
  description?: string | null;
}

export type EvaluationKnowledgeBaseResponse = KnowledgeBaseSummary;
export type EvaluationKnowledgeBaseListResponse = KnowledgeBaseListResponse;

export interface EvalDataset {
  id: number;
  name: string;
  description: string | null;
  knowledge_base_id: number;
  version: string;
  status: EvalDatasetStatus;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface EvalDatasetListResponse {
  items: EvalDataset[];
  total: number;
  page: number;
  page_size: number;
}

export interface EvalDatasetPayload {
  name: string;
  description?: string | null;
  knowledge_base_id: number;
  version: string;
  status: EvalDatasetStatus;
}

export interface EvalCase {
  id: number;
  dataset_id: number;
  question: string;
  expected_answer: string;
  expected_doc_ids: number[];
  expected_snippets: string[];
  expected_chunk_ids: number[];
  expected_evidence: EvalRetrievedDocumentEvidence[];
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface EvalCaseListResponse {
  items: EvalCase[];
  total: number;
}

export interface EvalCasePayload {
  question: string;
  expected_answer: string;
  expected_doc_ids: number[];
  expected_snippets: string[];
  expected_chunk_ids: number[];
  enabled: boolean;
}

export interface EvalCaseImportItem {
  row_number: number;
  question: string;
  expected_answer: string;
  expected_evidence: string | null;
}

export interface EvalCaseImportError {
  row_number: number;
  field: string | null;
  message: string;
}

export interface EvalCaseImportPreview {
  total_rows: number;
  valid_cases: EvalCaseImportItem[];
  errors: EvalCaseImportError[];
  can_import: boolean;
}

export interface EvalCaseImportResult {
  imported_count: number;
}

export interface EvalChunkCandidate {
  chunk_id: number;
  document_id: number;
  document_title: string;
  chunk_index: number;
  content: string;
  section_path: string | null;
  score: number;
}

export interface EvalChunkSearchResponse {
  items: EvalChunkCandidate[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

export interface EvalRun {
  id: number;
  dataset_id: number;
  run_name: string | null;
  status: EvalRunStatus;
  model_config: Record<string, unknown>;
  kb_snapshot: Record<string, unknown>;
  assistant_snapshot: Record<string, unknown>;
  case_snapshot: Record<string, unknown>;
  policy_snapshot: Record<string, unknown>;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  average_score: number;
  started_at: string | null;
  finished_at: string | null;
  heartbeat_at: string | null;
  error_message: string | null;
  created_by: number | null;
  created_at: string;
}

export interface EvalRunListItem extends EvalRun {
  dataset_name: string;
  dataset_version: string;
  knowledge_base_id: number;
}

export interface EvalRunPayload {
  run_name?: string | null;
  assistant_id: number;
}

export interface EvalDatasetBulkRunResponse {
  items: EvalRun[];
  total: number;
}

export interface EvalRunListResponse {
  items: EvalRunListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface EvalCaseResult {
  id: number;
  run_id: number;
  case_id: number;
  status: EvalCaseResultStatus;
  score: number;
  actual_answer: string;
  retrieved_doc_ids: number[];
  retrieved_chunk_ids: number[];
  judge_result: Record<string, unknown>;
  case_snapshot: Record<string, unknown>;
  latency_ms: number | null;
  error_message: string | null;
  created_at: string;
  retrieved_evidence: EvalRetrievedDocumentEvidence[];
}

export interface EvalRetrievedChunkEvidence {
  chunk_id: number;
  chunk_index: number;
  section_path: string | null;
  content: string;
}

export interface EvalRetrievedDocumentEvidence {
  document_id: number;
  document_title: string;
  chunks: EvalRetrievedChunkEvidence[];
}

export interface EvalCaseRetrievedEvidenceResponse {
  items: EvalRetrievedDocumentEvidence[];
}

export interface EvalRunDetail extends EvalRun {
  results: EvalCaseResult[];
  result_total: number;
  result_page: number;
  result_page_size: number;
}
