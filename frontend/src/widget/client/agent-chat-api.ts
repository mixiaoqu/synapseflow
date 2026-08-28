import {
  AppRequestError,
  DEFAULT_HTTP_ERROR_MESSAGE,
  DEFAULT_NETWORK_ERROR_MESSAGE,
  resolveHttpErrorMessage,
} from "../errors";

export interface WidgetPageContext {
  schema_version: 1;
  page_type: string;
  route_name?: string;
  route_path?: string;
  entity_type?: string;
  entity_id?: string;
  entity_name?: string;
  attributes?: Record<string, unknown>;
}

export interface WidgetPageConfig {
  page_type: string;
  page_name: string;
  page_description: string;
  assistant_intro: string;
  suggested_questions: string[];
}

export interface WidgetBootstrap {
  project_name: string;
  app_name: string;
  assistant_name: string;
  welcome_message?: string | null;
  placeholder_text?: string | null;
  suggested_prompts: string[];
  page_config?: WidgetPageConfig | null;
}

export interface WidgetSessionMessage {
  role: string;
  content: string;
  retrieved_docs?: Array<Record<string, unknown>>;
  answer_status?: string | null;
  log_id?: number | null;
  created_at: string;
}

export interface WidgetSessionSummary {
  session_id: string;
  title: string;
  preview?: string | null;
  created_at: string;
  updated_at: string;
}

export interface WidgetSessionDetail extends WidgetSessionSummary {
  messages: WidgetSessionMessage[];
}

export interface WidgetChatPayload {
  query: string;
  session_id?: string | null;
  page_context: WidgetPageContext;
}

function buildHeaders(token: string, hasBody: boolean) {
  const headers = new Headers({ Authorization: `Bearer ${token}` });
  if (hasBody) {
    headers.set("Content-Type", "application/json");
  }
  return headers;
}

async function parsePayload(response: Response): Promise<unknown> {
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

async function request(
  apiBaseUrl: string,
  endpoint: string,
  options: { token: string; method?: string; body?: unknown; signal?: AbortSignal },
) {
  try {
    const response = await fetch(`${apiBaseUrl}${endpoint}`, {
      method: options.method ?? "GET",
      headers: buildHeaders(options.token, options.body !== undefined),
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    });
    if (!response.ok) {
      const details = await parsePayload(response);
      throw new AppRequestError(
        resolveHttpErrorMessage(response.status, details, DEFAULT_HTTP_ERROR_MESSAGE),
        { status: response.status, details },
      );
    }
    return response;
  } catch (error) {
    if (error instanceof AppRequestError) {
      throw error;
    }
    throw new AppRequestError(DEFAULT_NETWORK_ERROR_MESSAGE, {
      isNetworkError: true,
      originalError: error,
    });
  }
}

async function getJson<T>(
  apiBaseUrl: string,
  endpoint: string,
  options: { token: string; method?: string; body?: unknown },
) {
  const response = await request(apiBaseUrl, endpoint, options);
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function createAgentChatApi(apiBaseUrl: string) {
  const normalizedBaseUrl = apiBaseUrl.trim().replace(/\/+$/, "");
  if (!normalizedBaseUrl) {
    throw new Error("AgentChat apiBaseUrl is required.");
  }

  return {
    bootstrap(token: string, pageContext: WidgetPageContext) {
      const query = new URLSearchParams({ page_type: pageContext.page_type });
      return getJson<WidgetBootstrap>(
        normalizedBaseUrl,
        `/widget/bootstrap?${query.toString()}`,
        { token },
      );
    },

    listSessions(token: string, limit = 30) {
      return getJson<WidgetSessionSummary[]>(
        normalizedBaseUrl,
        `/widget/sessions?limit=${limit}`,
        { token },
      );
    },

    getSession(token: string, sessionId: string) {
      return getJson<WidgetSessionDetail>(
        normalizedBaseUrl,
        `/widget/sessions/${encodeURIComponent(sessionId)}`,
        { token },
      );
    },

    deleteSession(token: string, sessionId: string) {
      return getJson<void>(
        normalizedBaseUrl,
        `/widget/sessions/${encodeURIComponent(sessionId)}`,
        { token, method: "DELETE" },
      );
    },

    async stream(token: string, payload: WidgetChatPayload, signal: AbortSignal) {
      const response = await request(normalizedBaseUrl, "/widget/stream", {
        token,
        method: "POST",
        body: payload,
        signal,
      });
      if (!response.body) {
        throw new AppRequestError("响应数据为空。");
      }
      return response.body;
    },

    submitFeedback(token: string, logId: number, feedbackValue: string) {
      return getJson<{ message: string }>(
        normalizedBaseUrl,
        `/widget/feedback/${logId}`,
        {
          token,
          method: "POST",
          body: { feedback_value: feedbackValue },
        },
      );
    },
  };
}

export type AgentChatApi = ReturnType<typeof createAgentChatApi>;
