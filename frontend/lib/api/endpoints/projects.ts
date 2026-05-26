import { apiClient } from "../client";

export interface ProjectResponse {
  id: number;
  team_id: number;
  team_name?: string | null;
  product_id: number;
  product_code?: string | null;
  product_name?: string | null;
  code: string;
  name: string;
  description?: string | null;
  is_active: boolean;
  app_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectPayload {
  name: string;
  code: string;
  team_id: number;
  product_id: number;
  description?: string | null;
  is_active: boolean;
}

export interface ProjectAppResponse {
  id: number;
  project_id: number;
  code: string;
  name: string;
  description?: string | null;
  default_assistant_id?: number | null;
  default_assistant_name?: string | null;
  knowledge_base_id?: number | null;
  knowledge_base_name?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectAppPayload {
  code: string;
  name: string;
  description?: string | null;
  knowledge_base_id: number;
  default_assistant_id?: number | null;
  is_active: boolean;
}

export interface ProjectAppEmbedPreviewResponse {
  embed_url: string;
  expires_in_seconds: number;
}

export const projectsApi = {
  list: (filters?: { team_id?: number | null }) => {
    const params = new URLSearchParams();
    if (filters?.team_id != null) params.set("team_id", String(filters.team_id));
    return apiClient.get<ProjectResponse[]>(
      `/api/v1/projects${params.size > 0 ? `?${params.toString()}` : ""}`,
    );
  },

  get: (projectId: number) =>
    apiClient.get<ProjectResponse>(`/api/v1/projects/${projectId}`),

  create: (payload: ProjectPayload) =>
    apiClient.post<ProjectResponse>("/api/v1/projects", payload),

  update: (projectId: number, payload: ProjectPayload) =>
    apiClient.put<ProjectResponse>(`/api/v1/projects/${projectId}`, payload),

  delete: (projectId: number) =>
    apiClient.delete<{ message: string }>(`/api/v1/projects/${projectId}`),

  listApps: (projectId: number) =>
    apiClient.get<ProjectAppResponse[]>(`/api/v1/projects/${projectId}/apps`),

  getApp: (projectId: number, appId: number) =>
    apiClient.get<ProjectAppResponse>(`/api/v1/projects/${projectId}/apps/${appId}`),

  createApp: (projectId: number, payload: ProjectAppPayload) =>
    apiClient.post<ProjectAppResponse>(`/api/v1/projects/${projectId}/apps`, payload),

  updateApp: (projectId: number, appId: number, payload: ProjectAppPayload) =>
    apiClient.put<ProjectAppResponse>(
      `/api/v1/projects/${projectId}/apps/${appId}`,
      payload,
    ),

  createEmbedPreview: (projectId: number, appId: number) =>
    apiClient.post<ProjectAppEmbedPreviewResponse>(
      `/api/v1/projects/${projectId}/apps/${appId}/embed-preview`,
      {},
    ),

  deleteApp: (projectId: number, appId: number) =>
    apiClient.delete<{ message: string }>(
      `/api/v1/projects/${projectId}/apps/${appId}`,
    ),
};
