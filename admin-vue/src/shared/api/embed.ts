import {
  API_BASE_URL,
  DEFAULT_HTTP_ERROR_MESSAGE,
  DEFAULT_NETWORK_ERROR_MESSAGE,
} from "@/shared/api/config";
import { AppRequestError } from "@/shared/utils/error";

export interface EmbedPageConfig {
  page_type: string;
  page_name: string;
  page_description: string;
  assistant_intro: string;
  suggested_questions: string[];
}

export interface EmbedAssistantBootstrap {
  product_id: number;
  product_code: string;
  product_name: string;
  project_id: number;
  project_code: string;
  project_name: string;
  project_app_id: number;
  app_code: string;
  app_name: string;
  assistant_id: number;
  assistant_name: string;
  welcome_message?: string | null;
  placeholder_text?: string | null;
  suggested_prompts: string[];
  page_config?: EmbedPageConfig | null;
}

export interface EmbedPageContext {
  app_id?: string | null;
  page_type: string;
}

export interface EmbedAssistantStreamPayload {
  query: string;
  session_id?: string | null;
  page_context?: EmbedPageContext | null;
}

export interface EmbedFeedbackPayload {
  feedback_value: string;
  feedback_note?: string | null;
}

function buildEmbedHeaders(token: string, hasBody: boolean) {
  const headers = new Headers({
    Authorization: `Bearer ${token}`,
  });

  if (hasBody) {
    headers.set("Content-Type", "application/json");
  }

  return headers;
}

function extractMessage(input: unknown): string | null {
  if (typeof input === "string") {
    const value = input.trim();
    return value || null;
  }

  if (Array.isArray(input)) {
    for (const item of input) {
      const message = extractMessage(item);
      if (message) {
        return message;
      }
    }
    return null;
  }

  if (input && typeof input === "object") {
    const payload = input as Record<string, unknown>;
    return (
      extractMessage(payload.detail) ??
      extractMessage(payload.message) ??
      extractMessage(payload.error) ??
      null
    );
  }

  return null;
}

async function parseResponsePayload(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

async function handleFailure(response: Response): Promise<never> {
  const payload = await parseResponsePayload(response);
  throw new AppRequestError(
    extractMessage(payload) ?? response.statusText ?? DEFAULT_HTTP_ERROR_MESSAGE,
    {
      status: response.status,
      details: payload,
    },
  );
}

async function embedFetch(
  endpoint: string,
  options: {
    token: string;
    method?: string;
    body?: unknown;
    signal?: AbortSignal;
  },
) {
  try {
    return await fetch(`${API_BASE_URL}${endpoint}`, {
      method: options.method ?? "GET",
      headers: buildEmbedHeaders(options.token, options.body !== undefined),
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    });
  } catch (error) {
    throw new AppRequestError(DEFAULT_NETWORK_ERROR_MESSAGE, {
      isNetworkError: true,
      originalError: error,
    });
  }
}

async function getJson<T>(
  endpoint: string,
  options: {
    token: string;
    method?: string;
    body?: unknown;
    signal?: AbortSignal;
  },
): Promise<T> {
  const response = await embedFetch(endpoint, options);
  if (!response.ok) {
    return handleFailure(response);
  }

  return (await response.json()) as T;
}

async function getStream(
  endpoint: string,
  options: {
    token: string;
    body: unknown;
    signal?: AbortSignal;
  },
): Promise<ReadableStream<Uint8Array>> {
  const response = await embedFetch(endpoint, {
    token: options.token,
    method: "POST",
    body: options.body,
    signal: options.signal,
  });

  if (!response.ok) {
    return handleFailure(response);
  }

  if (!response.body) {
    throw new AppRequestError("响应数据为空。");
  }

  return response.body;
}

export const embedApi = {
  bootstrap(token: string) {
    return getJson<EmbedAssistantBootstrap>("/embed/assistant/bootstrap", {
      token,
    });
  },

  stream(token: string, payload: EmbedAssistantStreamPayload, signal?: AbortSignal) {
    return getStream("/embed/assistant/stream", {
      token,
      body: payload,
      signal,
    });
  },

  submitFeedback(token: string, logId: number, payload: EmbedFeedbackPayload) {
    return getJson<{ message: string }>(`/embed/assistant/feedback/${logId}`, {
      token,
      method: "POST",
      body: payload,
    });
  },
};
