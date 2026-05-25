export interface ScopeInput {
  productCode?: string;
  projectCode?: string;
  appCode?: string;
}

export interface ResolvedScope {
  productCode: string;
  projectCode: string;
  appCode: string;
}

export interface AppConfig {
  baseUrl: string;
  accessToken?: string;
  serviceToken?: string;
  defaultProductCode?: string;
  defaultProjectCode?: string;
  defaultAppCode?: string;
  editorName: string;
  clientUserId?: string;
  clientUserName?: string;
  clientHost?: string;
}

function normalizeOptional(value: string | undefined): string | undefined {
  const normalized = value?.trim();
  return normalized ? normalized : undefined;
}

function requireEnv(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export function loadConfig(): AppConfig {
  const accessToken = normalizeOptional(process.env.SYNAPSEFLOW_ACCESS_TOKEN);
  const serviceToken = normalizeOptional(process.env.SYNAPSEFLOW_SERVICE_TOKEN);
  if (!accessToken && !serviceToken) {
    throw new Error(
      "Missing authentication configuration. Provide SYNAPSEFLOW_ACCESS_TOKEN or SYNAPSEFLOW_SERVICE_TOKEN.",
    );
  }
  return {
    baseUrl: requireEnv("SYNAPSEFLOW_BASE_URL").replace(/\/+$/, ""),
    accessToken,
    serviceToken,
    defaultProductCode: normalizeOptional(process.env.SYNAPSEFLOW_DEFAULT_PRODUCT),
    defaultProjectCode: normalizeOptional(process.env.SYNAPSEFLOW_DEFAULT_PROJECT),
    defaultAppCode: normalizeOptional(process.env.SYNAPSEFLOW_DEFAULT_APP),
    editorName: normalizeOptional(process.env.MCP_EDITOR) ?? "unknown",
    clientUserId: normalizeOptional(process.env.SYNAPSEFLOW_CLIENT_USER_ID),
    clientUserName: normalizeOptional(process.env.SYNAPSEFLOW_CLIENT_USER_NAME),
    clientHost: normalizeOptional(process.env.SYNAPSEFLOW_CLIENT_HOST),
  };
}

export function hasDefaultScope(config: AppConfig): boolean {
  return Boolean(
    config.defaultProductCode && config.defaultProjectCode && config.defaultAppCode,
  );
}

export function resolveScopeInput(config: AppConfig, input: ScopeInput): ResolvedScope {
  const productCode = normalizeOptional(input.productCode) ?? config.defaultProductCode;
  const projectCode = normalizeOptional(input.projectCode) ?? config.defaultProjectCode;
  const appCode = normalizeOptional(input.appCode) ?? config.defaultAppCode;

  if (!productCode || !projectCode || !appCode) {
    throw new Error(
      "Missing scope parameters. Provide product_code, project_code, app_code or configure SYNAPSEFLOW_DEFAULT_PRODUCT, SYNAPSEFLOW_DEFAULT_PROJECT, SYNAPSEFLOW_DEFAULT_APP.",
    );
  }

  return {
    productCode,
    projectCode,
    appCode,
  };
}
