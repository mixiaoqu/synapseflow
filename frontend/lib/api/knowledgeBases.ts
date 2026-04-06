import { apiClient } from "./client";
import type { DocumentIndexStatus } from "./documents";

export interface KnowledgeBaseBase {
  id: number;
  name: string;
  team_id: number;
  description?: string | null;
  created_at: string;
  updated_at: string;
}

export type KnowledgeBaseStatus = "available" | "indexing" | "error" | "empty";

export interface KnowledgeBaseRecentDocument {
  id: number;
  title: string;
  document_type: string | null;
  size: number;
  indexed: boolean;
  index_status: DocumentIndexStatus;
  index_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeBaseWithCount extends KnowledgeBaseBase {
  document_count: number;
  indexed_document_count: number;
  queued_document_count: number;
  processing_document_count: number;
  failed_document_count: number;
  unindexed_document_count: number;
  last_document_updated_at: string | null;
  last_uploaded_at: string | null;
  status: KnowledgeBaseStatus;
  recent_documents: KnowledgeBaseRecentDocument[];
}

export async function listKnowledgeBases(
  teamId?: number | null,
): Promise<KnowledgeBaseWithCount[]> {
  const sp = new URLSearchParams();
  if (teamId != null) sp.set("team_id", String(teamId));
  const q = sp.toString();
  return apiClient.get(`/api/v1/knowledge-bases${q ? `?${q}` : ""}`);
}

export async function createKnowledgeBase(
  name: string,
  teamId: number,
  description?: string | null,
): Promise<KnowledgeBaseBase> {
  return apiClient.post("/api/v1/knowledge-bases", {
    name,
    team_id: teamId,
    description,
  });
}

export async function updateKnowledgeBase(
  knowledgeBaseId: number,
  payload: {
    name: string;
    description?: string | null;
  },
): Promise<KnowledgeBaseBase> {
  return apiClient.put(`/api/v1/knowledge-bases/${knowledgeBaseId}`, payload);
}

export async function deleteKnowledgeBase(knowledgeBaseId: number): Promise<void> {
  await apiClient.delete(`/api/v1/knowledge-bases/${knowledgeBaseId}`);
}
