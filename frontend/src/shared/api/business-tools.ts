import { request } from "@/shared/api/http";
import type {
  BusinessApi,
  BusinessApiListResponse,
  BusinessApiPayload,
  BusinessConnection,
  BusinessConnectionListResponse,
  BusinessConnectionPayload,
  BusinessConnectionTestResponse,
  BusinessTool,
  BusinessToolCallLogListResponse,
  BusinessToolImplementation,
  BusinessToolImplementationListResponse,
  BusinessToolImplementationPayload,
  BusinessToolListResponse,
  BusinessToolPayload,
  BusinessToolPublishResponse,
  BusinessToolTestPayload,
  BusinessToolTestResponse,
  ProjectAppBusinessToolBinding,
  ProjectAppBusinessToolBindingListResponse,
  ProjectAppBusinessToolBindingPayload,
} from "@/shared/types/business-tool";

export function listBusinessConnections(params: {
  team_id?: number;
  keyword?: string;
  status?: "all" | "untested" | "available" | "error";
  page: number;
  page_size: number;
}) {
  return request<BusinessConnectionListResponse>({
    url: "/business-tools/connections",
    method: "GET",
    params,
  });
}

export function createBusinessConnection(payload: BusinessConnectionPayload) {
  return request<BusinessConnection>({
    url: "/business-tools/connections",
    method: "POST",
    data: payload,
  });
}

export function updateBusinessConnection(connectionId: number, payload: BusinessConnectionPayload) {
  return request<BusinessConnection>({
    url: `/business-tools/connections/${connectionId}`,
    method: "PUT",
    data: payload,
  });
}

export function testBusinessConnection(connectionId: number) {
  return request<BusinessConnectionTestResponse>({
    url: `/business-tools/connections/${connectionId}/test`,
    method: "POST",
  });
}

export function deleteBusinessConnection(connectionId: number) {
  return request<{ message: string }>({
    url: `/business-tools/connections/${connectionId}`,
    method: "DELETE",
  });
}

export function listBusinessApis(params: {
  team_id?: number;
  keyword?: string;
  enabled_status?: "all" | "enabled" | "disabled";
  connection_id?: number;
  page: number;
  page_size: number;
}) {
  return request<BusinessApiListResponse>({
    url: "/business-tools/apis",
    method: "GET",
    params,
  });
}

export function getBusinessApi(apiId: number) {
  return request<BusinessApi>({
    url: `/business-tools/apis/${apiId}`,
    method: "GET",
  });
}

export function createBusinessApi(payload: BusinessApiPayload) {
  return request<BusinessApi>({
    url: "/business-tools/apis",
    method: "POST",
    data: payload,
  });
}

export function updateBusinessApi(apiId: number, payload: BusinessApiPayload) {
  return request<BusinessApi>({
    url: `/business-tools/apis/${apiId}`,
    method: "PUT",
    data: payload,
  });
}

export function deleteBusinessApi(apiId: number) {
  return request<{ message: string }>({
    url: `/business-tools/apis/${apiId}`,
    method: "DELETE",
  });
}

export function listBusinessTools(params: {
  team_id?: number;
  keyword?: string;
  enabled_status?: "all" | "enabled" | "disabled";
  lifecycle_status?: "all" | "draft" | "verified" | "published" | "error";
  connection_id?: number;
  page: number;
  page_size: number;
}) {
  return request<BusinessToolListResponse>({
    url: "/business-tools",
    method: "GET",
    params,
  });
}

export function getBusinessTool(toolId: number) {
  return request<BusinessTool>({
    url: `/business-tools/${toolId}`,
    method: "GET",
  });
}

export function createBusinessTool(payload: BusinessToolPayload) {
  return request<BusinessTool>({
    url: "/business-tools",
    method: "POST",
    data: payload,
  });
}

export function updateBusinessTool(toolId: number, payload: BusinessToolPayload) {
  return request<BusinessTool>({
    url: `/business-tools/${toolId}`,
    method: "PUT",
    data: payload,
  });
}

export function listBusinessToolImplementations(toolId: number) {
  return request<BusinessToolImplementationListResponse>({
    url: `/business-tools/${toolId}/implementations`,
    method: "GET",
  });
}

export function createBusinessToolImplementation(toolId: number, payload: BusinessToolImplementationPayload) {
  return request<BusinessToolImplementation>({
    url: `/business-tools/${toolId}/implementations`,
    method: "POST",
    data: payload,
  });
}

export function updateBusinessToolImplementation(
  implementationId: number,
  payload: BusinessToolImplementationPayload,
) {
  return request<BusinessToolImplementation>({
    url: `/business-tools/implementations/${implementationId}`,
    method: "PUT",
    data: payload,
  });
}

export function deleteBusinessToolImplementation(implementationId: number) {
  return request<{ message: string }>({
    url: `/business-tools/implementations/${implementationId}`,
    method: "DELETE",
  });
}

export function testBusinessTool(toolId: number, payload: BusinessToolTestPayload) {
  return request<BusinessToolTestResponse>({
    url: `/business-tools/${toolId}/test`,
    method: "POST",
    data: payload,
  });
}

export function publishBusinessTool(toolId: number) {
  return request<BusinessToolPublishResponse>({
    url: `/business-tools/${toolId}/publish`,
    method: "POST",
  });
}

export function unpublishBusinessTool(toolId: number) {
  return request<BusinessToolPublishResponse>({
    url: `/business-tools/${toolId}/unpublish`,
    method: "POST",
  });
}

export function deleteBusinessTool(toolId: number) {
  return request<{ message: string }>({
    url: `/business-tools/${toolId}`,
    method: "DELETE",
  });
}

export function listBusinessToolCallLogs(params: {
  team_id?: number;
  tool_id?: number;
  project_app_id?: number;
  status?: "all" | "success" | "error";
  started_at?: string;
  ended_at?: string;
  page: number;
  page_size: number;
}) {
  return request<BusinessToolCallLogListResponse>({
    url: "/business-tools/logs",
    method: "GET",
    params,
  });
}

export function listProjectAppBusinessToolBindings(projectId: number, appId: number) {
  return request<ProjectAppBusinessToolBindingListResponse>({
    url: `/business-tools/project-apps/${projectId}/${appId}/bindings`,
    method: "GET",
  });
}

export function bindProjectAppBusinessTool(
  projectId: number,
  appId: number,
  payload: ProjectAppBusinessToolBindingPayload,
) {
  return request<ProjectAppBusinessToolBinding>({
    url: `/business-tools/project-apps/${projectId}/${appId}/bindings`,
    method: "POST",
    data: payload,
  });
}

export function unbindProjectAppBusinessTool(projectId: number, appId: number, bindingId: number) {
  return request<{ message: string }>({
    url: `/business-tools/project-apps/${projectId}/${appId}/bindings/${bindingId}`,
    method: "DELETE",
  });
}
