import { AppConfig, ResolvedScope } from "./config.js";

interface JsonRequestOptions {
  path: string;
  body: Record<string, unknown>;
  token: string;
}

interface McpBootstrapResponse {
  access_token: string;
  expires_in_seconds: number;
  scope: {
    product_code: string;
    project_code: string;
    app_code: string;
  };
}

interface CachedBootstrapToken {
  accessToken: string;
  expiresAtMs: number;
  scopeKey: string;
}

let cachedBootstrapToken: CachedBootstrapToken | null = null;

function buildScopeKey(scope: ResolvedScope): string {
  return `${scope.productCode}::${scope.projectCode}::${scope.appCode}`;
}

async function postJson<T>(config: AppConfig, options: JsonRequestOptions): Promise<T> {
  const response = await fetch(`${config.baseUrl}/api/v1/mcp${options.path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${options.token}`,
      "X-Client-Channel": "mcp",
      "X-Client-Editor": config.editorName,
    },
    body: JSON.stringify(options.body),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`LangChain RAG 知识库 MCP request failed (${response.status}): ${text}`);
  }

  return (await response.json()) as T;
}

async function bootstrapAccessToken(
  config: AppConfig,
  scope: ResolvedScope,
): Promise<string> {
  if (!config.serviceToken) {
    throw new Error("SYNAPSEFLOW_SERVICE_TOKEN is required for MCP bootstrap mode.");
  }

  const scopeKey = buildScopeKey(scope);
  const now = Date.now();
  if (cachedBootstrapToken && cachedBootstrapToken.scopeKey === scopeKey) {
    const refreshBeforeMs = 2 * 60 * 1000;
    if (cachedBootstrapToken.expiresAtMs - refreshBeforeMs > now) {
      return cachedBootstrapToken.accessToken;
    }
  }

  const bootstrap = await postJson<McpBootstrapResponse>(config, {
    path: "/bootstrap",
    token: config.serviceToken,
    body: {
      product_code: scope.productCode,
      project_code: scope.projectCode,
      app_code: scope.appCode,
      client_user_id: config.clientUserId,
      client_user_name: config.clientUserName,
      client_editor: config.editorName,
      client_host: config.clientHost,
    },
  });

  cachedBootstrapToken = {
    accessToken: bootstrap.access_token,
    expiresAtMs: now + bootstrap.expires_in_seconds * 1000,
    scopeKey,
  };
  return bootstrap.access_token;
}

async function resolveAuthToken(config: AppConfig, scope: ResolvedScope): Promise<string> {
  if (config.serviceToken) {
    return bootstrapAccessToken(config, scope);
  }
  if (config.accessToken) {
    return config.accessToken;
  }
  throw new Error(
    "Missing authentication configuration. Provide SYNAPSEFLOW_ACCESS_TOKEN or SYNAPSEFLOW_SERVICE_TOKEN.",
  );
}

export async function resolveScope(
  config: AppConfig,
  scope: ResolvedScope,
): Promise<Record<string, unknown>> {
  const token = await resolveAuthToken(config, scope);
  return postJson(config, {
    path: "/scope/resolve",
    token,
    body: {
      product_code: scope.productCode,
      project_code: scope.projectCode,
      app_code: scope.appCode,
    },
  });
}

export async function searchKnowledge(
  config: AppConfig,
  scope: ResolvedScope,
  query: string,
  topK?: number,
): Promise<Record<string, unknown>> {
  const token = await resolveAuthToken(config, scope);
  return postJson(config, {
    path: "/search",
    token,
    body: {
      query,
      product_code: scope.productCode,
      project_code: scope.projectCode,
      app_code: scope.appCode,
      top_k: topK,
    },
  });
}

export async function answerKnowledge(
  config: AppConfig,
  scope: ResolvedScope,
  query: string,
): Promise<Record<string, unknown>> {
  const token = await resolveAuthToken(config, scope);
  return postJson(config, {
    path: "/answer",
    token,
    body: {
      query,
      product_code: scope.productCode,
      project_code: scope.projectCode,
      app_code: scope.appCode,
    },
  });
}
