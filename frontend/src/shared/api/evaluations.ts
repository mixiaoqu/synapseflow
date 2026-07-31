import { request } from "@/shared/api/http";
import type {
  EvalCase,
  EvalCaseListResponse,
  EvalCasePayload,
  EvalChunkSearchResponse,
  EvalDataset,
  EvalDatasetBulkRunResponse,
  EvalDatasetListResponse,
  EvalDatasetPayload,
  EvalRun,
  EvalRunDetail,
  EvalRunListResponse,
  EvalRunPayload,
  EvaluationKnowledgeBaseListResponse,
  EvaluationKnowledgeBasePayload,
  EvaluationKnowledgeBaseResponse,
} from "@/modules/evaluations/types";

export function listEvaluationKnowledgeBases(params: {
  team_id?: number;
  active_only?: boolean;
  keyword?: string;
  page: number;
  page_size: number;
}) {
  return request<EvaluationKnowledgeBaseListResponse>({
    url: "/evaluations/knowledge-bases",
    method: "GET",
    params: {
      ...(params.team_id ? { team_id: params.team_id } : {}),
      ...(params.active_only ? { active_only: true } : {}),
      ...(params.keyword?.trim() ? { keyword: params.keyword.trim() } : {}),
      page: params.page,
      page_size: params.page_size,
    },
  });
}

export function createEvaluationKnowledgeBase(payload: EvaluationKnowledgeBasePayload) {
  return request<EvaluationKnowledgeBaseResponse>({
    url: "/evaluations/knowledge-bases",
    method: "POST",
    data: payload,
  });
}

export function listEvalDatasets(params: {
  keyword?: string;
  page: number;
  page_size: number;
}) {
  return request<EvalDatasetListResponse>({
    url: "/evaluations/datasets",
    method: "GET",
    params: {
      ...(params.keyword?.trim() ? { keyword: params.keyword.trim() } : {}),
      page: params.page,
      page_size: params.page_size,
    },
  });
}

export function createEvalDataset(payload: EvalDatasetPayload) {
  return request<EvalDataset>({
    url: "/evaluations/datasets",
    method: "POST",
    data: payload,
  });
}

export function updateEvalDataset(datasetId: number, payload: EvalDatasetPayload) {
  return request<EvalDataset>({
    url: `/evaluations/datasets/${datasetId}`,
    method: "PUT",
    data: payload,
  });
}

export function getEvalDataset(datasetId: number) {
  return request<EvalDataset>({
    url: `/evaluations/datasets/${datasetId}`,
    method: "GET",
  });
}

export function listEvalCases(datasetId: number) {
  return request<EvalCaseListResponse>({
    url: `/evaluations/datasets/${datasetId}/cases`,
    method: "GET",
  });
}

export function createEvalCase(datasetId: number, payload: EvalCasePayload) {
  return request<EvalCase>({
    url: `/evaluations/datasets/${datasetId}/cases`,
    method: "POST",
    data: payload,
  });
}

export function updateEvalCase(datasetId: number, caseId: number, payload: EvalCasePayload) {
  return request<EvalCase>({
    url: `/evaluations/datasets/${datasetId}/cases/${caseId}`,
    method: "PUT",
    data: payload,
  });
}

export function deleteEvalCase(datasetId: number, caseId: number) {
  return request<{ message: string }>({
    url: `/evaluations/datasets/${datasetId}/cases/${caseId}`,
    method: "DELETE",
  });
}

export function bulkDeleteEvalCases(datasetId: number, caseIds: number[]) {
  return request<{ deleted_count: number }>({
    url: `/evaluations/datasets/${datasetId}/cases/bulk-delete`,
    method: "POST",
    data: {
      case_ids: caseIds,
    },
  });
}

export function searchEvalChunks(datasetId: number, params: { query?: string; offset?: number; limit?: number }) {
  return request<EvalChunkSearchResponse>({
    url: `/evaluations/datasets/${datasetId}/chunks`,
    method: "GET",
    params: {
      ...(params.query?.trim() ? { query: params.query.trim() } : {}),
      ...(params.offset ? { offset: params.offset } : {}),
      ...(params.limit ? { limit: params.limit } : {}),
    },
  });
}

export function executeEvalDataset(datasetId: number, payload: EvalRunPayload) {
  return request<EvalRun>({
    url: `/evaluations/datasets/${datasetId}/runs`,
    method: "POST",
    data: payload,
  });
}

export function bulkRunEvalDatasets(datasetIds: number[], payload: EvalRunPayload) {
  return request<EvalDatasetBulkRunResponse>({
    url: "/evaluations/datasets/bulk-runs",
    method: "POST",
    data: {
      dataset_ids: datasetIds,
      run_name: payload.run_name ?? null,
      assistant_id: payload.assistant_id,
    },
  });
}

export function listEvalRuns(params: {
  keyword?: string;
  status?: string;
  dataset_id?: number;
  page: number;
  page_size: number;
}) {
  return request<EvalRunListResponse>({
    url: "/evaluations/runs",
    method: "GET",
    params: {
      ...(params.keyword?.trim() ? { keyword: params.keyword.trim() } : {}),
      ...(params.status?.trim() ? { status: params.status.trim() } : {}),
      ...(params.dataset_id ? { dataset_id: params.dataset_id } : {}),
      page: params.page,
      page_size: params.page_size,
    },
  });
}

export function getEvalRunDetail(runId: number) {
  return request<EvalRunDetail>({
    url: `/evaluations/runs/${runId}`,
    method: "GET",
  });
}
