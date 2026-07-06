import { request } from "@/shared/api/http";
import type {
  ProjectBulkAction,
  ProjectBulkActionResponse,
  ProjectAppBulkAction,
  ProjectAppBulkActionResponse,
  ProjectAppEmbedPreviewPayload,
  ProjectAppEmbedPreviewResponse,
  ProjectAppListResponse,
  ProjectAppSummary,
  ProjectAppUpsertPayload,
  ProjectCopyPayload,
  ProjectListResponse,
  ProjectSummary,
  ProjectUpsertPayload,
} from "@/shared/types/project";

export function listProjects(params: {
  team_id?: number;
  product_id?: number;
  keyword?: string;
  status?: "all" | "active" | "inactive";
  page: number;
  page_size: number;
}) {
  return request<ProjectListResponse>({
    url: "/projects",
    method: "GET",
    params,
  });
}

export function getProject(projectId: number) {
  return request<ProjectSummary>({
    url: `/projects/${projectId}`,
    method: "GET",
  });
}

export function createProject(payload: ProjectUpsertPayload) {
  return request<ProjectSummary>({
    url: "/projects",
    method: "POST",
    data: payload,
  });
}

export function copyProject(projectId: number, payload: ProjectCopyPayload) {
  return request<ProjectSummary>({
    url: `/projects/${projectId}/copy`,
    method: "POST",
    data: payload,
  });
}

export function deleteProject(projectId: number) {
  return request<{ message: string }>({
    url: `/projects/${projectId}`,
    method: "DELETE",
  });
}

export function bulkActionProjects(projectIds: number[], action: ProjectBulkAction) {
  return request<ProjectBulkActionResponse>({
    url: "/projects/bulk-action",
    method: "POST",
    data: {
      project_ids: projectIds,
      action,
    },
  });
}

export function listProjectApps(projectId: number, params: {
  keyword?: string;
  status?: "all" | "active" | "inactive";
  page: number;
  page_size: number;
}) {
  return request<ProjectAppListResponse>({
    url: `/projects/${projectId}/apps`,
    method: "GET",
    params,
  });
}

export function getProjectApp(projectId: number, appId: number) {
  return request<ProjectAppSummary>({
    url: `/projects/${projectId}/apps/${appId}`,
    method: "GET",
  });
}

export function createProjectApp(projectId: number, payload: ProjectAppUpsertPayload) {
  return request<ProjectAppSummary>({
    url: `/projects/${projectId}/apps`,
    method: "POST",
    data: payload,
  });
}

export function updateProjectApp(
  projectId: number,
  appId: number,
  payload: ProjectAppUpsertPayload,
) {
  return request<ProjectAppSummary>({
    url: `/projects/${projectId}/apps/${appId}`,
    method: "PUT",
    data: payload,
  });
}

export function deleteProjectApp(projectId: number, appId: number) {
  return request<{ message: string }>({
    url: `/projects/${projectId}/apps/${appId}`,
    method: "DELETE",
  });
}

export function bulkActionProjectApps(
  projectId: number,
  appIds: number[],
  action: ProjectAppBulkAction,
) {
  return request<ProjectAppBulkActionResponse>({
    url: `/projects/${projectId}/apps/bulk-action`,
    method: "POST",
    data: {
      app_ids: appIds,
      action,
    },
  });
}

export function createProjectAppEmbedPreview(
  projectId: number,
  appId: number,
  payload: ProjectAppEmbedPreviewPayload = {},
) {
  return request<ProjectAppEmbedPreviewResponse>({
    url: `/projects/${projectId}/apps/${appId}/embed-preview`,
    method: "POST",
    data: payload,
  });
}
