import { apiClient } from "./client";

export interface Team {
  id: number;
  name: string;
  code?: string | null;
  description?: string | null;
  created_at: string;
  updated_at: string;
}

export async function listTeams(): Promise<Team[]> {
  return apiClient.get("/api/v1/teams");
}
