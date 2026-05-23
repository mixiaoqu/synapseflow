import { request } from "@/shared/api/http";
import type {
  BatchDocumentActionResponse,
  DocumentChunksResponse,
  DocumentDetail,
  DocumentLifecycleStatus,
  DocumentListResponse,
  DocumentQueueResponse,
} from "@/shared/types/document";

export function listDocuments(params: {
  page?: number;
  page_size?: number;
  keyword?: string;
  team_id?: number;
  knowledge_base_id?: number;
  category_id?: number;
  status?: DocumentLifecycleStatus;
}) {
  return request<DocumentListResponse>({
    url: "/documents",
    method: "GET",
    params,
  });
}

export function getDocument(docId: number) {
  return request<DocumentDetail>({
    url: `/documents/detail/${docId}`,
    method: "GET",
  });
}

export function getDocumentChunks(docId: number) {
  return request<DocumentChunksResponse>({
    url: `/documents/${docId}/chunks`,
    method: "GET",
  });
}

export function uploadDocumentsBatch(payload: {
  files: File[];
  knowledgeBaseId: number;
  categoryId?: number | null;
  sourcePaths?: string[];
}) {
  const form = new FormData();
  payload.files.forEach((file, index) => {
    form.append("files", file);
    const sourcePath = payload.sourcePaths?.[index];
    if (sourcePath) {
      form.append("source_paths", sourcePath);
    }
  });
  form.append("knowledge_base_id", String(payload.knowledgeBaseId));
  if (payload.categoryId) {
    form.append("category_id", String(payload.categoryId));
  }

  return request<DocumentDetail[], FormData>({
    url: "/documents/batch",
    method: "POST",
    data: form,
  });
}

export function deleteDocument(docId: number) {
  return request<{ message: string }>({
    url: `/documents/${docId}`,
    method: "DELETE",
  });
}

export function deleteDocumentsBatch(ids: number[]) {
  return request<{ message: string; deleted: number }>({
    url: "/documents/batch/delete",
    method: "DELETE",
    params: {
      ids,
    },
    paramsSerializer: {
      serialize(params) {
        const searchParams = new URLSearchParams();
        const values = Array.isArray(params.ids) ? params.ids : [];
        values.forEach((value) => {
          searchParams.append("ids", String(value));
        });
        return searchParams.toString();
      },
    },
  });
}

export function indexDocument(docId: number) {
  return request<DocumentQueueResponse>({
    url: `/documents/${docId}/index`,
    method: "POST",
  });
}

export function submitDocumentForReview(docId: number) {
  return request<DocumentDetail>({
    url: `/documents/${docId}/submit-for-review`,
    method: "POST",
  });
}

export function submitDocumentsForReviewBatch(ids: number[]) {
  return request<BatchDocumentActionResponse, { ids: number[] }>({
    url: "/documents/batch/submit-for-review",
    method: "POST",
    data: { ids },
  });
}

export function submitDocumentsForReviewByFilter(payload: {
  keyword?: string;
  team_id?: number;
  knowledge_base_id?: number;
  category_id?: number;
}) {
  return request<BatchDocumentActionResponse, typeof payload>({
    url: "/documents/batch/submit-for-review-by-filter",
    method: "POST",
    data: payload,
  });
}

export function rejectDocument(docId: number) {
  return request<DocumentDetail>({
    url: `/documents/${docId}/reject`,
    method: "POST",
  });
}

export function rejectDocumentsBatch(ids: number[]) {
  return request<BatchDocumentActionResponse, { ids: number[] }>({
    url: "/documents/batch/reject",
    method: "POST",
    data: { ids },
  });
}

export function publishDocument(docId: number) {
  return request<DocumentDetail>({
    url: `/documents/${docId}/publish`,
    method: "POST",
  });
}

export function publishDocumentsBatch(ids: number[]) {
  return request<BatchDocumentActionResponse, { ids: number[] }>({
    url: "/documents/batch/publish",
    method: "POST",
    data: { ids },
  });
}

export function publishDocumentsByFilter(payload: {
  keyword?: string;
  team_id?: number;
  knowledge_base_id?: number;
  category_id?: number;
}) {
  return request<BatchDocumentActionResponse, typeof payload>({
    url: "/documents/batch/publish-by-filter",
    method: "POST",
    data: payload,
  });
}

export function unpublishDocument(docId: number) {
  return request<DocumentDetail>({
    url: `/documents/${docId}/unpublish`,
    method: "POST",
  });
}

export function unpublishDocumentsBatch(ids: number[]) {
  return request<BatchDocumentActionResponse, { ids: number[] }>({
    url: "/documents/batch/unpublish",
    method: "POST",
    data: { ids },
  });
}
