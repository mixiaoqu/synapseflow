import { request } from "@/shared/api/http";
import { apiConfig } from "@/shared/api/config";
import { consumeSseStream, type SseEnvelope } from "@/shared/lib/stream/sse";
import { clearAuthSession, getAccessToken } from "@/shared/auth/session";
import type { AssistantPreviewResponse } from "@/shared/types/assistant";

export interface QaPreviewPayload {
  query: string;
  team_id: number;
  knowledge_base_id: number;
  assistant_id?: number | null;
  include_unpublished: boolean;
}

export function previewQa(payload: QaPreviewPayload) {
  return request<AssistantPreviewResponse>({
    url: "/admin/qa/preview",
    method: "POST",
    data: payload,
  });
}

async function readErrorMessage(response: Response) {
  const raw = await response.text();
  if (!raw) {
    return `测试请求失败（${response.status}）`;
  }

  try {
    const payload = JSON.parse(raw) as { detail?: string; message?: string };
    return payload.detail || payload.message || raw;
  } catch {
    return raw;
  }
}

export async function streamQa(
  payload: QaPreviewPayload,
  onEvent: (event: SseEnvelope) => void,
  signal?: AbortSignal,
) {
  const headers = new Headers({ "Content-Type": "application/json" });
  const token = getAccessToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${apiConfig.baseURL}/admin/qa/preview/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
    signal,
  });

  if (response.status === 401) {
    clearAuthSession();
  }
  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }
  if (!response.body) {
    throw new Error("测试响应为空。");
  }

  await consumeSseStream(response.body, onEvent);
}
