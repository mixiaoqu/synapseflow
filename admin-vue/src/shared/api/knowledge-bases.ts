import { request } from "@/shared/api/http";
import type { KnowledgeBaseSummary } from "@/shared/types/knowledge-base";

export interface KnowledgeBasePayload {
  name: string;
  description?: string | null;
}

export interface CreateKnowledgeBasePayload extends KnowledgeBasePayload {
  team_id: number;
}

export function listKnowledgeBases(teamId?: number) {
  return request<KnowledgeBaseSummary[]>({
    url: "/knowledge-bases",
    method: "GET",
    params: teamId ? { team_id: teamId } : undefined,
  });
}

export function createKnowledgeBase(payload: CreateKnowledgeBasePayload) {
  return request<KnowledgeBaseSummary>({
    url: "/knowledge-bases",
    method: "POST",
    data: payload,
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

export function reindexKnowledgeBaseDocuments(knowledgeBaseId: number) {
  return request({
    url: "/documents/reindex-all",
    method: "POST",
    params: {
      knowledge_base_id: knowledgeBaseId,
    },
  });
}
