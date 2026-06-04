const FALLBACK_API_BASE_URL = "http://localhost:8000/api/v1";
const FALLBACK_TIMEOUT_MS = 15_000;

// 统一清理末尾斜杠，避免接口路径拼接时出现双斜杠。
function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, "");
}

function resolveTimeout(value: string | undefined, fallback: number) {
  const parsed = Number(value);

  if (Number.isFinite(parsed) && parsed > 0) {
    return parsed;
  }

  return fallback;
}

export const API_BASE_URL = trimTrailingSlash(
  import.meta.env.VITE_API_BASE_URL ?? FALLBACK_API_BASE_URL,
);

export const HTTP_TIMEOUT = resolveTimeout(
  import.meta.env.VITE_API_TIMEOUT_MS,
  FALLBACK_TIMEOUT_MS,
);

export const DEFAULT_HTTP_ERROR_MESSAGE = "请求失败，请稍后重试。";
export const DEFAULT_NETWORK_ERROR_MESSAGE = "网络连接失败，请检查服务后重试。";

export const apiConfig = {
  baseURL: API_BASE_URL,
  timeout: HTTP_TIMEOUT,
} as const;
