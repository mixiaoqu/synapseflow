export const DEFAULT_HTTP_ERROR_MESSAGE = "请求失败，请稍后重试。";
export const DEFAULT_NETWORK_ERROR_MESSAGE = "网络连接失败，请检查服务后重试。";

interface ErrorPayload {
  detail?: unknown;
  message?: unknown;
  error?: unknown;
}

const STATUS_ERROR_MESSAGES: Record<number, string> = {
  400: "提交内容有误，请检查后重试。",
  401: "登录已失效，请重新登录。",
  403: "当前账号没有权限执行此操作。",
  404: "请求的内容不存在，可能已被删除。",
  409: "当前操作与已有数据冲突，请检查后重试。",
  422: "填写内容有误，请检查后重试。",
  429: "操作过于频繁，请稍后再试。",
};

export class AppRequestError extends Error {
  status?: number;
  details?: unknown;
  isNetworkError: boolean;
  originalError?: unknown;

  constructor(
    message: string,
    options: {
      status?: number;
      details?: unknown;
      isNetworkError?: boolean;
      originalError?: unknown;
    } = {},
  ) {
    super(message);
    this.name = "AppRequestError";
    this.status = options.status;
    this.details = options.details;
    this.isNetworkError = options.isNetworkError ?? false;
    this.originalError = options.originalError;
  }
}

function extractMessage(input: unknown): string | null {
  if (typeof input === "string") return input.trim() || null;
  if (Array.isArray(input)) {
    for (const item of input) {
      const message = extractMessage(item);
      if (message) return message;
    }
    return null;
  }
  if (input && typeof input === "object") {
    const payload = input as ErrorPayload;
    return (
      extractMessage(payload.detail) ??
      extractMessage(payload.message) ??
      extractMessage(payload.error)
    );
  }
  return null;
}

function isSafeUserMessage(message: string) {
  const value = message.trim();
  return (
    Boolean(value) &&
    /[\u4e00-\u9fa5]/.test(value) &&
    !/(traceback|exception|stack|sql|constraint|undefined|pydantic|validation|[A-Za-z_]+Error)/i.test(
      value,
    )
  );
}

export function resolveHttpErrorMessage(
  status: number | undefined,
  details: unknown,
  fallbackMessage = DEFAULT_HTTP_ERROR_MESSAGE,
) {
  const rawMessage = extractMessage(details);
  if (rawMessage && isSafeUserMessage(rawMessage)) return rawMessage;
  if (!status) return fallbackMessage;
  if (status >= 500) return "服务暂时不可用，请稍后重试。";
  return STATUS_ERROR_MESSAGES[status] ?? fallbackMessage;
}

export function resolveDisplayErrorMessage(
  message: string | null | undefined,
  fallbackMessage: string,
) {
  return message && isSafeUserMessage(message) ? message.trim() : fallbackMessage;
}
