import { request } from "@/shared/api/http";
import type {
  AgentTool,
  AgentToolBatchPublishResponse,
  AgentToolGrant,
  AgentToolGrantListResponse,
  AgentToolInvocationListResponse,
  AgentToolListResponse,
  AgentToolPublishResponse,
  AgentToolSyncResponse,
  AgentToolTestResponse,
  AgentToolUpdatePayload,
  ProjectAppAccessCreatePayload,
  ProjectAppAccessCredential,
  ProjectAppAccessIssuedCredential,
  ProjectAppAccessUpdatePayload,
  ToolProvider,
  ToolProviderListResponse,
  ToolProviderPayload,
  ToolProviderTestResponse,
} from "@/shared/types/agent-integration";

export function getProjectAppAccess(projectId: number, appId: number) {
  return request<ProjectAppAccessCredential>({
    url: `/agent-integrations/project-apps/${projectId}/${appId}/access`,
    method: "GET",
  });
}

export function createProjectAppAccess(projectId: number, appId: number, payload: ProjectAppAccessCreatePayload) {
  return request<ProjectAppAccessIssuedCredential>({
    url: `/agent-integrations/project-apps/${projectId}/${appId}/access`,
    method: "POST",
    data: payload,
  });
}

export function updateProjectAppAccess(projectId: number, appId: number, payload: ProjectAppAccessUpdatePayload) {
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

export function listToolProviders(params: {
  team_id: number;
  keyword?: string;
  health_status?: string;
  page?: number;
  page_size?: number;
}) {
  return request<ToolProviderListResponse>({ url: "/agent-integrations/tool-providers", method: "GET", params });
}

export function createToolProvider(payload: ToolProviderPayload) {
  return request<ToolProvider>({ url: "/agent-integrations/tool-providers", method: "POST", data: payload });
}

export function updateToolProvider(providerId: number, payload: ToolProviderPayload) {
  return request<ToolProvider>({
    url: `/agent-integrations/tool-providers/${providerId}`,
    method: "PUT",
    data: payload,
  });
}

export function deleteToolProvider(providerId: number) {
  return request<{ message: string }>({
    url: `/agent-integrations/tool-providers/${providerId}`,
    method: "DELETE",
  });
}

export function testToolProvider(providerId: number) {
  return request<ToolProviderTestResponse>({
    url: `/agent-integrations/tool-providers/${providerId}/test`,
    method: "POST",
  });
}

export function syncAgentTools(providerId: number) {
  return request<AgentToolSyncResponse>({
    url: `/agent-integrations/tool-providers/${providerId}/sync`,
    method: "POST",
  });
}

export function listAgentTools(params: {
  team_id: number;
  provider_id?: number;
  keyword?: string;
  publish_status?: string;
  sync_status?: string;
  page?: number;
  page_size?: number;
}) {
  return request<AgentToolListResponse>({ url: "/agent-integrations/agent-tools", method: "GET", params });
}

export function updateAgentTool(toolId: number, payload: AgentToolUpdatePayload) {
  return request<AgentTool>({ url: `/agent-integrations/agent-tools/${toolId}`, method: "PUT", data: payload });
}

export function testAgentTool(
  toolId: number,
  argumentsPayload: Record<string, unknown>,
  context: Record<string, unknown>,
) {
  return request<AgentToolTestResponse>({
    url: `/agent-integrations/agent-tools/${toolId}/test`,
    method: "POST",
    data: { arguments: argumentsPayload, context },
  });
}

export function publishAgentTool(toolId: number) {
  return request<AgentToolPublishResponse>({
    url: `/agent-integrations/agent-tools/${toolId}/publish`,
    method: "POST",
  });
}

export function batchPublishAgentTools(toolIds: number[]) {
  return request<AgentToolBatchPublishResponse>({
    url: "/agent-integrations/agent-tools/batch-publish",
    method: "POST",
    data: { tool_ids: toolIds },
  });
}

export function unpublishAgentTool(toolId: number) {
  return request<AgentToolPublishResponse>({
    url: `/agent-integrations/agent-tools/${toolId}/unpublish`,
    method: "POST",
  });
}

export function listProjectAppToolGrants(projectId: number, appId: number) {
  return request<AgentToolGrantListResponse>({
    url: `/agent-integrations/project-apps/${projectId}/${appId}/tool-grants`,
    method: "GET",
  });
}

export function replaceProjectAppToolGrants(projectId: number, appId: number, agentToolIds: number[]) {
  return request<AgentToolGrantListResponse>({
    url: `/agent-integrations/project-apps/${projectId}/${appId}/tool-grants`,
    method: "PUT",
    data: { agent_tool_ids: agentToolIds },
  });
}

export function createProjectAppToolGrant(projectId: number, appId: number, agentToolId: number) {
  return request<AgentToolGrant>({
    url: `/agent-integrations/project-apps/${projectId}/${appId}/tool-grants`,
    method: "POST",
    data: { agent_tool_id: agentToolId },
  });
}

export function deleteProjectAppToolGrant(projectId: number, appId: number, grantId: number) {
  return request<{ message: string }>({
    url: `/agent-integrations/project-apps/${projectId}/${appId}/tool-grants/${grantId}`,
    method: "DELETE",
  });
}

export function listAgentToolInvocations(params: {
  team_id: number;
  agent_tool_id?: number;
  project_app_id?: number;
  status?: string;
  started_at?: string;
  ended_at?: string;
  page?: number;
  page_size?: number;
}) {
  return request<AgentToolInvocationListResponse>({
    url: "/agent-integrations/tool-invocations",
    method: "GET",
    params,
  });
}
