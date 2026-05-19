import { request } from "@/shared/api/http";
import type {
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
}) {
  const form = new FormData();
  for (const file of payload.files) {
    form.append("files", file);
  }
  form.append("knowledge_base_id", String(payload.knowledgeBaseId));
  if (payload.categoryId) {
    form.append("category_id", String(payload.categoryId));
  }

  return request<DocumentDetail[], FormData>({
    url: "/documents/batch",
    method: "POST",
    data: form,
    headers: {
      "Content-Type": "multipart/form-data",
    },
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
  });
}

export function indexDocument(docId: number) {
  return request<DocumentQueueResponse>({
    url: `/documents/${docId}/index`,
    method: "POST",
  });
}
