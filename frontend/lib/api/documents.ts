import { apiClient } from "./client";

export type DocumentIndexStatus = "queued" | "processing" | "indexed" | "failed";
export type DocumentLifecycleStatus =
  | "draft"
  | "pending_review"
  | "published"
  | "archived";

export type DocumentListItem = {
  id: number;
  title: string;
  document_type: string | null;
  size: number;
  version: number;
  is_current: boolean;
  is_latest: boolean;
  is_live: boolean;
  indexed: boolean;
  index_status: DocumentIndexStatus;
  index_error: string | null;
  indexed_at: string | null;
  knowledge_base_id: number | null;
  knowledge_base_branch_id: number | null;
  knowledge_base_branch_name: string | null;
  knowledge_base_name: string | null;
  category_id: number | null;
  category_name: string | null;
  source_path: string | null;
  status: DocumentLifecycleStatus;
  published_at: string | null;
  published_by: number | null;
  reviewed_at: string | null;
  reviewed_by: number | null;
  created_at: string;
  updated_at: string;
};

export type DocumentDetail = {
  id: number;
  title: string;
  content: string;
  document_type: string | null;
  size: number;
  version: number;
  is_current: boolean;
  is_latest: boolean;
  is_live: boolean;
  knowledge_base_id: number | null;
  knowledge_base_branch_id: number | null;
  knowledge_base_branch_name: string | null;
  category_id: number | null;
  category_name: string | null;
  source_path: string | null;
  status: DocumentLifecycleStatus;
  published_at: string | null;
  published_by: number | null;
  reviewed_at: string | null;
  reviewed_by: number | null;
  index_status: DocumentIndexStatus;
  index_error: string | null;
  indexed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type DocumentVersionItem = {
  id: number;
  title: string;
  version: number;
  is_latest: boolean;
  is_current: boolean;
  is_live: boolean;
  created_at: string;
};

export type DocumentIndexQueueResponse = {
  message: string;
  queued: number;
};

export type ActiveIndexingJob = {
  job_id: number;
  title: string;
  job_type: string;
  job_status: "queued" | "processing" | "completed" | "partial_failed" | "failed";
  knowledge_base_id: number | null;
  knowledge_base_name: string | null;
  queued: number;
  processing: number;
  indexed: number;
  failed: number;
  total: number;
  created_at: string;
  updated_at: string | null;
  progress_percent: number;
};

export type FailedIndexingItem = {
  job_id: number;
  document_id: number;
  title: string;
  job_title: string;
  knowledge_base_id: number | null;
  knowledge_base_name: string | null;
  index_error: string | null;
  updated_at: string;
};

export type IndexingPanelSummary = {
  queued: number;
  processing: number;
  indexed: number;
  failed: number;
  total: number;
  has_active: boolean;
  active_job_count: number;
  active_jobs: ActiveIndexingJob[];
  recent_failed: FailedIndexingItem[];
};

export async function listDocuments(params: {
  page?: number;
  page_size?: number;
  keyword?: string | null;
  team_id?: number | null;
  knowledge_base_id?: number | null;
  knowledge_base_branch_id?: number | null;
  category_id?: number | null;
  status?: DocumentLifecycleStatus | null;
}): Promise<{
  items: DocumentListItem[];
  total: number;
  page: number;
  page_size: number;
}> {
  const sp = new URLSearchParams();
  if (params.page != null) sp.set("page", String(params.page));
  if (params.page_size != null) sp.set("page_size", String(params.page_size));
  if (params.keyword) sp.set("keyword", params.keyword);
  if (params.team_id !== undefined && params.team_id !== null) {
    sp.set("team_id", String(params.team_id));
  }
  if (params.knowledge_base_id !== undefined && params.knowledge_base_id !== null) {
    sp.set("knowledge_base_id", String(params.knowledge_base_id));
  }
  if (params.knowledge_base_branch_id !== undefined && params.knowledge_base_branch_id !== null) {
    sp.set("knowledge_base_branch_id", String(params.knowledge_base_branch_id));
  }
  if (params.category_id !== undefined && params.category_id !== null) {
    sp.set("category_id", String(params.category_id));
  }
  if (params.status) {
    sp.set("status", params.status);
  }

  const q = sp.toString();
  return apiClient.get(`/api/v1/documents${q ? `?${q}` : ""}`);
}

export async function getIndexingPanelSummary(): Promise<IndexingPanelSummary> {
  return apiClient.get("/api/v1/documents/indexing/panel-summary");
}

export async function getDocument(docId: number): Promise<DocumentDetail> {
  return apiClient.get(`/api/v1/documents/detail/${docId}`);
}

export async function getDocumentVersions(docId: number): Promise<DocumentVersionItem[]> {
  const data = await apiClient.get<{ items: DocumentVersionItem[] }>(
    `/api/v1/documents/${docId}/versions`,
  );
  return data.items;
}

export async function uploadDocument(
  file: File,
  knowledgeBaseId?: number | null,
  knowledgeBaseBranchId?: number | null,
  options?: {
    categoryId?: number | null;
    sourcePath?: string | null;
  },
): Promise<DocumentDetail> {
  const form = new FormData();
  form.append("file", file);
  if (knowledgeBaseId != null && knowledgeBaseId > 0) {
    form.append("knowledge_base_id", String(knowledgeBaseId));
  }
  if (knowledgeBaseBranchId != null && knowledgeBaseBranchId > 0) {
    form.append("knowledge_base_branch_id", String(knowledgeBaseBranchId));
  }
  if (options?.categoryId != null && options.categoryId > 0) {
    form.append("category_id", String(options.categoryId));
  }
  if (options?.sourcePath) {
    form.append("source_path", options.sourcePath);
  }
  return apiClient.postForm("/api/v1/documents", form);
}

export async function uploadDocumentsBatch(
  files: File[],
  knowledgeBaseId?: number | null,
  knowledgeBaseBranchId?: number | null,
  options?: {
    categoryId?: number | null;
    sourcePaths?: Array<string | null | undefined>;
  },
): Promise<DocumentDetail[]> {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  if (knowledgeBaseId != null && knowledgeBaseId > 0) {
    form.append("knowledge_base_id", String(knowledgeBaseId));
  }
  if (knowledgeBaseBranchId != null && knowledgeBaseBranchId > 0) {
    form.append("knowledge_base_branch_id", String(knowledgeBaseBranchId));
  }
  if (options?.categoryId != null && options.categoryId > 0) {
    form.append("category_id", String(options.categoryId));
  }
  for (const sourcePath of options?.sourcePaths ?? []) {
    if (sourcePath) form.append("source_paths", sourcePath);
  }
  return apiClient.postForm("/api/v1/documents/batch", form);
}

export async function createDocumentFromContent(body: {
  title: string;
  content: string;
  document_type?: string;
  knowledge_base_id?: number | null;
  knowledge_base_branch_id: number;
  category_id?: number | null;
  source_path?: string | null;
}): Promise<DocumentDetail> {
  return apiClient.post("/api/v1/documents/from-content", body);
}

export async function replaceDocumentContent(
  docId: number,
  content: string,
): Promise<DocumentDetail> {
  return apiClient.put(`/api/v1/documents/${docId}/content`, { content });
}

export async function createDocumentVersion(
  docId: number,
  content: string,
): Promise<DocumentDetail> {
  return apiClient.post(`/api/v1/documents/${docId}/versions`, { content });
}

export async function switchCurrentDocumentVersion(docId: number): Promise<DocumentDetail> {
  return apiClient.post(`/api/v1/documents/${docId}/current`, {});
}

export async function indexDocument(
  docId: number,
): Promise<DocumentIndexQueueResponse> {
  return apiClient.post(`/api/v1/documents/${docId}/index`, {});
}

export async function reindexAll(params?: {
  team_id?: number | null;
  knowledge_base_id?: number | null;
}): Promise<DocumentIndexQueueResponse> {
  const sp = new URLSearchParams();
  if (params?.team_id != null) sp.set("team_id", String(params.team_id));
  if (params?.knowledge_base_id != null) {
    sp.set("knowledge_base_id", String(params.knowledge_base_id));
  }
  const q = sp.toString();
  return apiClient.post(`/api/v1/documents/reindex-all${q ? `?${q}` : ""}`, {});
}

export async function deleteDocument(docId: number): Promise<void> {
  await apiClient.delete(`/api/v1/documents/${docId}`);
}

export async function deleteDocumentsBatch(
  ids: number[],
): Promise<{ message: string; deleted: number }> {
  const sp = new URLSearchParams();
  for (const id of ids) sp.append("ids", String(id));
  return apiClient.delete(`/api/v1/documents/batch/delete?${sp.toString()}`);
}

export async function submitDocumentForReview(docId: number): Promise<DocumentDetail> {
  return apiClient.post(`/api/v1/documents/${docId}/submit-for-review`, {});
}

export async function rejectDocument(docId: number): Promise<DocumentDetail> {
  return apiClient.post(`/api/v1/documents/${docId}/reject`, {});
}

export async function publishDocument(docId: number): Promise<DocumentDetail> {
  return apiClient.post(`/api/v1/documents/${docId}/publish`, {});
}

export async function unpublishDocument(docId: number): Promise<DocumentDetail> {
  return apiClient.post(`/api/v1/documents/${docId}/unpublish`, {});
}
