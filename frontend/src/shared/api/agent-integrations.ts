import { request } from "@/shared/api/http";
import type {
  AgentAppToolSetBinding,
  AgentAppToolSetBindingListResponse,
  AgentAppToolSetBindingPayload,
  AgentTool,
  AgentToolCallLogListResponse,
  AgentToolListResponse,
  AgentToolPayload,
  AgentToolPublishResponse,
  AgentToolTestResponse,
  McpServer,
  McpServerListResponse,
  McpServerPayload,
  McpServerTestResponse,
  McpToolListResponse,
  McpTool,
  McpToolSyncResponse,
  ProjectAppAccessCreatePayload,
  ProjectAppAccessCredential,
  ProjectAppAccessIssuedCredential,
  ProjectAppAccessUpdatePayload,
} from "@/shared/types/agent-integration";

export function getProjectAppAccess(projectId: number, appId: number) {
  return request<ProjectAppAccessCredential>({
    url: `/agent-integrations/project-apps/${projectId}/${appId}/access`,
    method: "GET",
  });
}

export function createProjectAppAccess(
  projectId: number,
  appId: number,
  payload: ProjectAppAccessCreatePayload,
) {
  return request<ProjectAppAccessIssuedCredential>({
    url: `/agent-integrations/project-apps/${projectId}/${appId}/access`,
    method: "POST",
    data: payload,
  });
}

export function updateProjectAppAccess(
  projectId: number,
  appId: number,
  payload: ProjectAppAccessUpdatePayload,
) {
  return request<ProjectAppAccessCredential>({
    url: `/agent-integrations/project-apps/${projectId}/${appId}/access`,
    method: "PUT",
    data: payload,
  });
}

export function resetProjectAppAccessSecret(projectId: number, appId: number) {
  return request<ProjectAppAccessIssuedCredential>({
    url: `/agent-integrations/project-apps/${projectId}/${appId}/access/reset-secret`,
    method: "POST",
  });
}

export function enableProjectAppAccess(projectId: number, appId: number) {
  return request<ProjectAppAccessCredential>({
    url: `/agent-integrations/project-apps/${projectId}/${appId}/access/enable`,
    method: "POST",
  });
}

export function revokeProjectAppAccess(projectId: number, appId: number) {
  return request<ProjectAppAccessCredential>({
    url: `/agent-integrations/project-apps/${projectId}/${appId}/access/revoke`,
    method: "POST",
  });
}

export function listMcpServers(params: {
  team_id?: number;
  keyword?: string;
  status?: string;
  page?: number;
  page_size?: number;
}) {
  return request<McpServerListResponse>({ url: "/agent-integrations/mcp-servers", method: "GET", params });
}

export function createMcpServer(payload: McpServerPayload) {
  return request<McpServer>({ url: "/agent-integrations/mcp-servers", method: "POST", data: payload });
}

export function updateMcpServer(serverId: number, payload: McpServerPayload) {
  return request<McpServer>({ url: `/agent-integrations/mcp-servers/${serverId}`, method: "PUT", data: payload });
}

export function deleteMcpServer(serverId: number) {
  return request<{ message: string }>({ url: `/agent-integrations/mcp-servers/${serverId}`, method: "DELETE" });
}

export function testMcpServer(serverId: number) {
  return request<McpServerTestResponse>({ url: `/agent-integrations/mcp-servers/${serverId}/test`, method: "POST" });
}

export function syncMcpTools(serverId: number) {
  return request<McpToolSyncResponse>({ url: `/agent-integrations/mcp-servers/${serverId}/sync`, method: "POST" });
}

export function listMcpTools(params: {
  team_id?: number;
  server_id?: number;
  keyword?: string;
  page?: number;
  page_size?: number;
}) {
  return request<McpToolListResponse>({ url: "/agent-integrations/mcp-tools", method: "GET", params });
}

export function updateMcpToolEnabled(toolId: number, enabled: boolean) {
  return request<McpTool>({
    url: `/agent-integrations/mcp-tools/${toolId}/enabled`,
    method: "PUT",
    data: { enabled },
  });
}

export function listAgentTools(params: {
  team_id?: number;
  keyword?: string;
  enabled_status?: string;
  lifecycle_status?: string;
  page?: number;
  page_size?: number;
}) {
  return request<AgentToolListResponse>({ url: "/agent-integrations/agent-tools", method: "GET", params });
}

export function createAgentTool(payload: AgentToolPayload) {
  return request<AgentTool>({ url: "/agent-integrations/agent-tools", method: "POST", data: payload });
}

export function updateAgentTool(toolId: number, payload: AgentToolPayload) {
  return request<AgentTool>({ url: `/agent-integrations/agent-tools/${toolId}`, method: "PUT", data: payload });
}

export function testAgentTool(toolId: number, argumentsPayload: Record<string, unknown>) {
  return request<AgentToolTestResponse>({
    url: `/agent-integrations/agent-tools/${toolId}/test`,
    method: "POST",
    data: { arguments: argumentsPayload },
  });
}

export function publishAgentTool(toolId: number) {
  return request<AgentToolPublishResponse>({ url: `/agent-integrations/agent-tools/${toolId}/publish`, method: "POST" });
}

export function unpublishAgentTool(toolId: number) {
  return request<AgentToolPublishResponse>({ url: `/agent-integrations/agent-tools/${toolId}/unpublish`, method: "POST" });
}

export function deleteAgentTool(toolId: number) {
  return request<{ message: string }>({ url: `/agent-integrations/agent-tools/${toolId}`, method: "DELETE" });
}

export function listProjectAppToolSetBindings(projectId: number, appId: number) {
  return request<AgentAppToolSetBindingListResponse>({
    url: `/agent-integrations/project-apps/${projectId}/${appId}/tool-sets`,
    method: "GET",
  });
}

export function bindProjectAppToolSet(projectId: number, appId: number, payload: AgentAppToolSetBindingPayload) {
  return request<AgentAppToolSetBinding>({
    url: `/agent-integrations/project-apps/${projectId}/${appId}/tool-sets`,
    method: "POST",
    data: payload,
  });
}

export function unbindProjectAppToolSet(projectId: number, appId: number, bindingId: number) {
  return request<{ message: string }>({
    url: `/agent-integrations/project-apps/${projectId}/${appId}/tool-sets/${bindingId}`,
    method: "DELETE",
  });
}

export function listAgentToolCallLogs(params: {
  team_id?: number;
  agent_tool_id?: number;
  project_app_id?: number;
  status?: string;
  started_at?: string;
  ended_at?: string;
  page?: number;
  page_size?: number;
}) {
  return request<AgentToolCallLogListResponse>({ url: "/agent-integrations/call-logs", method: "GET", params });
}
