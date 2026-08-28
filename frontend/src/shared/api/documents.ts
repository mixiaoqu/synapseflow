import { request } from "@/shared/api/http";
import type {
  BatchDocumentActionResponse,
  DocumentChunksResponse,
  DocumentDetail,
  DocumentUploadInitRequest,
  DocumentUploadInitResponse,
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

export function initDocumentUpload(payload: DocumentUploadInitRequest) {
  return request<DocumentUploadInitResponse, DocumentUploadInitRequest>({
    url: "/documents/uploads/init",
    method: "POST",
    data: payload,
  });
}

export function completeDocumentUpload(uploadSessionId: number) {
  return request<DocumentDetail, { upload_session_id: number }>({
    url: "/documents/uploads/complete",
    method: "POST",
    data: {
      upload_session_id: uploadSessionId,
    },
  });
}

export function abortDocumentUpload(uploadSessionId: number) {
  return request<{ upload_session_id: number; status: string; message: string }, { upload_session_id: number }>({
    url: "/documents/uploads/abort",
    method: "POST",
    data: {
      upload_session_id: uploadSessionId,
    },
  });
}

async function uploadFileToObjectStorage(policy: DocumentUploadInitResponse, file: File) {
  if ((policy.method || "POST").toUpperCase() === "PUT") {
    const response = await fetch(policy.upload_url, {
      method: "PUT",
      body: file,
      headers: policy.form_fields,
      mode: "cors",
    });
    if (response.ok) {
      return;
    }
    const errorText = (await response.text()).trim();
    throw new Error(errorText || `TOS 上传失败（HTTP ${response.status}）`);
  }

  const form = new FormData();
  Object.entries(policy.form_fields).forEach(([key, value]) => {
    form.append(key, value);
  });
  form.append("file", file);

  const response = await fetch(policy.upload_url, {
    method: policy.method || "POST",
    body: form,
    mode: "cors",
  });
  if (response.status === 204 || response.ok) {
    return;
  }

  const errorText = (await response.text()).trim();
  throw new Error(errorText || `OSS 上传失败（HTTP ${response.status}）`);
}

export function uploadDocumentsBatch(payload: {
  files: File[];
  knowledgeBaseId: number;
  categoryId?: number | null;
  sourcePaths?: string[];
}) {
  return (async () => {
    const createdDocuments: DocumentDetail[] = [];

    for (const [index, file] of payload.files.entries()) {
      const sourcePath = payload.sourcePaths?.[index] ?? null;
      const uploadSession = await initDocumentUpload({
        filename: file.name,
        file_size: file.size,
        content_type: file.type || null,
        knowledge_base_id: payload.knowledgeBaseId,
        category_id: payload.categoryId ?? null,
        source_path: sourcePath,
      });

      try {
        await uploadFileToObjectStorage(uploadSession, file);
      } catch (error) {
        try {
          await abortDocumentUpload(uploadSession.upload_session_id);
        } catch {
          // 中止会话失败不覆盖原始上传错误。
        }
        const message = error instanceof Error ? error.message : "上传文档失败，请稍后重试。";
        throw new Error(`文件“${file.name}”上传失败：${message}`);
      }

      try {
        const document = await completeDocumentUpload(uploadSession.upload_session_id);
        createdDocuments.push(document);
      } catch (error) {
        const message = error instanceof Error ? error.message : "确认上传失败，请稍后重试。";
        throw new Error(`文件“${file.name}”确认上传失败：${message}`);
      }
    }

    return createdDocuments;
  })();
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
