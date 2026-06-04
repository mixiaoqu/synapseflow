import { request } from "@/shared/api/http";
import type {
  AssistantBulkAction,
  AssistantBulkActionResponse,
  AssistantDependencyUsage,
  AssistantDetail,
  AssistantModelOption,
  AssistantPreviewPayload,
  AssistantPreviewResponse,
  AssistantSummary,
  AssistantUpsertPayload,
} from "@/shared/types/assistant";

export function listAssistants(filters?: {
  team_id?: number | null;
  active_only?: boolean;
}) {
  const params = new URLSearchParams();
  if (filters?.team_id != null) params.set("team_id", String(filters.team_id));
  if (filters?.active_only) params.set("active_only", "true");

  return request<AssistantSummary[]>({
    url: `/assistants${params.size > 0 ? `?${params.toString()}` : ""}`,
    method: "GET",
  });
}

export function getAssistant(assistantId: number) {
  return request<AssistantDetail>({
    url: `/assistants/${assistantId}`,
    method: "GET",
  });
}

export function createAssistant(payload: AssistantUpsertPayload) {
  return request<AssistantDetail>({
    url: "/assistants",
    method: "POST",
    data: payload,
  });
}

export function updateAssistant(assistantId: number, payload: AssistantUpsertPayload) {
  return request<AssistantDetail>({
    url: `/assistants/${assistantId}`,
    method: "PUT",
    data: payload,
  });
}

export function listAssistantModelOptions() {
  return request<{ items: AssistantModelOption[] }>({
    url: "/assistants/model-options",
    method: "GET",
  });
}

export function previewAssistant(payload: AssistantPreviewPayload) {
  return request<AssistantPreviewResponse>({
    url: "/assistants/preview",
    method: "POST",
    data: payload,
  });
}

export function getAssistantUsage(assistantId: number) {
  return request<AssistantDependencyUsage>({
    url: `/assistants/${assistantId}/usage`,
    method: "GET",
  });
}

export function bulkActionAssistants(
  assistantIds: number[],
  action: AssistantBulkAction,
  options?: { force?: boolean },
) {
  return request<AssistantBulkActionResponse>({
    url: "/assistants/bulk-action",
    method: "POST",
    data: {
      assistant_ids: assistantIds,
      action,
      force: options?.force ?? false,
    },
  });
}

export function deleteAssistant(assistantId: number, options?: { force?: boolean }) {
  return request<{ message: string }>({
    url: `/assistants/${assistantId}${options?.force ? "?force=true" : ""}`,
    method: "DELETE",
  });
}
