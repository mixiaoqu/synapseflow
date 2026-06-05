import { request } from "@/shared/api/http";
import type { KnowledgeBaseListResponse, KnowledgeBaseSummary } from "@/shared/types/knowledge-base";

export interface KnowledgeBasePayload {
  name: string;
  description?: string | null;
}

export interface CreateKnowledgeBasePayload extends KnowledgeBasePayload {
  team_id: number;
}

export function listKnowledgeBases(params: {
  team_id?: number;
  active_only?: boolean;
  keyword?: string;
  page: number;
  page_size: number;
}) {
  return request<KnowledgeBaseListResponse>({
    url: "/knowledge-bases",
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

export function createKnowledgeBase(payload: CreateKnowledgeBasePayload) {
  return request<KnowledgeBaseSummary>({
    url: "/knowledge-bases",
    method: "POST",
    data: payload,
  });
}

export function getKnowledgeBase(knowledgeBaseId: number) {
  return request<KnowledgeBaseSummary>({
    url: `/knowledge-bases/${knowledgeBaseId}`,
    method: "GET",
  });
}

export function updateKnowledgeBase(
  knowledgeBaseId: number,
  payload: KnowledgeBasePayload,
) {
  return request<KnowledgeBaseSummary>({
    url: `/knowledge-bases/${knowledgeBaseId}`,
    method: "PUT",
    data: payload,
  });
}

export function deleteKnowledgeBase(knowledgeBaseId: number) {
  return request<{ message: string }>({
    url: `/knowledge-bases/${knowledgeBaseId}`,
    method: "DELETE",
  });
}

export function toggleKnowledgeBaseActive(knowledgeBaseId: number, isActive: boolean) {
  return request<KnowledgeBaseSummary>({
    url: `/knowledge-bases/${knowledgeBaseId}/toggle-active`,
    method: "PATCH",
    data: { is_active: isActive },
  });
}

export function reindexKnowledgeBaseDocuments(knowledgeBaseId: number) {
  return request({
    url: "/documents/reindex-all",
    method: "POST",
    params: {
      knowledge_base_id: knowledgeBaseId,
    },
  });
}
