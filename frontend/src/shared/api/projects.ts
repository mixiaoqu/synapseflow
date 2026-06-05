import { request } from "@/shared/api/http";
import type {
  ProjectAppCopyPayload,
  ProjectAppEmbedPreviewResponse,
  ProjectAppSummary,
  ProjectAppUpsertPayload,
  ProjectSummary,
  ProjectUpsertPayload,
} from "@/shared/types/project";

export function listProjects(teamId?: number) {
  return request<ProjectSummary[]>({
    url: "/projects",
    method: "GET",
    params: teamId ? { team_id: teamId } : undefined,
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

export function listProjectApps(projectId: number) {
  return request<ProjectAppSummary[]>({
    url: `/projects/${projectId}/apps`,
    method: "GET",
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

export function copyProjectApp(projectId: number, appId: number, payload: ProjectAppCopyPayload) {
  return request<ProjectAppSummary>({
    url: `/projects/${projectId}/apps/${appId}/copy`,
    method: "POST",
    data: payload,
  });
}

export function deleteProjectApp(projectId: number, appId: number) {
  return request<{ message: string }>({
    url: `/projects/${projectId}/apps/${appId}`,
    method: "DELETE",
  });
}

export function createProjectAppEmbedPreview(projectId: number, appId: number) {
  return request<ProjectAppEmbedPreviewResponse>({
    url: `/projects/${projectId}/apps/${appId}/embed-preview`,
    method: "POST",
  });
}
