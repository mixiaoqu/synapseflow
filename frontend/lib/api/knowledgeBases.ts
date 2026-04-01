import { apiClient } from "./client";

export interface KnowledgeBaseWithCount {
  id: number;
  name: string;
  team_id: number;
  description?: string | null;
  document_count: number;
  created_at: string;
  updated_at: string;
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
): Promise<KnowledgeBaseWithCount> {
  return apiClient.post("/api/v1/knowledge-bases", {
    name,
    team_id: teamId,
    description,
  });
}
