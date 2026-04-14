import { apiClient } from "./client";

export interface TeamItem {
  id: number;
  name: string;
  code?: string | null;
  description?: string | null;
  created_at: string;
  updated_at: string;
}

export type Team = TeamItem;

export interface TeamMemberItem {
  id: number;
  team_id: number;
  user_id: number;
  role: string;
  created_at: string;
  updated_at: string;
}

export async function listTeams(): Promise<TeamItem[]> {
  return apiClient.get("/api/v1/teams");
}

export async function createTeam(payload: {
  name: string;
  code?: string | null;
  description?: string | null;
}): Promise<TeamItem> {
  return apiClient.post("/api/v1/teams", payload);
}

export async function updateTeam(
  teamId: number,
  payload: { name: string; code?: string | null; description?: string | null },
): Promise<TeamItem> {
  return apiClient.put(`/api/v1/teams/${teamId}`, payload);
}

export async function deleteTeam(teamId: number): Promise<{ message: string }> {
  return apiClient.delete(`/api/v1/teams/${teamId}`);
}

export async function listTeamMembers(teamId: number): Promise<TeamMemberItem[]> {
  return apiClient.get(`/api/v1/teams/${teamId}/members`);
}

export async function addTeamMember(
  teamId: number,
  payload: { user_id: number; role: string },
): Promise<TeamMemberItem> {
  return apiClient.post(`/api/v1/teams/${teamId}/members`, payload);
}

export async function updateTeamMember(
  teamId: number,
  userId: number,
  payload: { role: string },
): Promise<TeamMemberItem> {
  return apiClient.put(`/api/v1/teams/${teamId}/members/${userId}`, payload);
}

export async function deleteTeamMember(
  teamId: number,
  userId: number,
): Promise<{ message: string }> {
  return apiClient.delete(`/api/v1/teams/${teamId}/members/${userId}`);
}
