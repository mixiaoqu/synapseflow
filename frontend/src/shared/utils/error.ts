import { isAxiosError } from "axios";

import {
  DEFAULT_HTTP_ERROR_MESSAGE,
  DEFAULT_NETWORK_ERROR_MESSAGE,
} from "@/shared/api/config";

interface ErrorPayload {
  code?: unknown;
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
  code?: string;
  details?: unknown;
  isNetworkError: boolean;
  originalError?: unknown;

  constructor(
    message: string,
    options: {
      status?: number;
      code?: string;
      details?: unknown;
      isNetworkError?: boolean;
      originalError?: unknown;
    } = {},
  ) {
    super(message);
    this.name = "AppRequestError";
    this.status = options.status;
    this.code = options.code;
    this.details = options.details;
    this.isNetworkError = options.isNetworkError ?? false;
    this.originalError = options.originalError;
  }
}

export function extractRawErrorMessage(input: unknown): string | null {
  if (typeof input === "string") {
    const value = input.trim();
    return value || null;
  }

  if (Array.isArray(input)) {
    for (const item of input) {
      const message = extractRawErrorMessage(item);
      if (message) {
        return message;
      }
    }

    return null;
  }

  if (input && typeof input === "object") {
    const payload = input as ErrorPayload;

    return (
      extractRawErrorMessage(payload.detail) ??
      extractRawErrorMessage(payload.message) ??
      extractRawErrorMessage(payload.error) ??
      null
    );
  }

  return null;
}

function isChineseUserMessage(message: string) {
  return /[\u4e00-\u9fa5]/.test(message);
}

function isTechnicalMessage(message: string) {
  return (
    /(^|\s)(traceback|exception|stack|sql|select|insert|update|delete|constraint|undefined|null|nan|timeout|http|axios|fetch|pydantic|validation|field|required|invalid|denied|not found|cannot|failed|error)(\s|:|$)/i.test(
      message,
    ) ||
    /[A-Za-z_]+Error\b/.test(message) ||
    /\b[A-Za-z_]+(\.[A-Za-z_]+)+\b/.test(message) ||
    /\b[A-Za-z_]+_[A-Za-z0-9_]+\b/.test(message)
  );
}

function isSafeBackendMessage(message: string) {
  const value = message.trim();
  return Boolean(value) && isChineseUserMessage(value) && !isTechnicalMessage(value);
}

export function resolveHttpErrorMessage(
  status: number | undefined,
  details: unknown,
  fallbackMessage = DEFAULT_HTTP_ERROR_MESSAGE,
) {
  const rawMessage = extractRawErrorMessage(details);

  if (rawMessage && isSafeBackendMessage(rawMessage)) {
    return rawMessage;
  }

  if (status) {
    if (status === 401 && rawMessage && /username|password|账号|密码/i.test(rawMessage)) {
      return "账号或密码不正确，请重新输入。";
    }

    if (status >= 500) {
      return "服务暂时不可用，请稍后重试。";
    }

    return STATUS_ERROR_MESSAGES[status] ?? fallbackMessage;
  }

  return fallbackMessage;
}

export function resolveDisplayErrorMessage(message: string | null | undefined, fallbackMessage: string) {
  if (!message) {
    return fallbackMessage;
  }

  return isSafeBackendMessage(message) ? message.trim() : fallbackMessage;
}

function extractCode(input: unknown) {
  if (!input || typeof input !== "object") {
    return undefined;
  }

  const payload = input as ErrorPayload;
  const code = payload.code;
  if (typeof code === "string" && code.trim()) {
    return code;
  }

  if (payload.detail && typeof payload.detail === "object") {
    return extractCode(payload.detail);
  }

  return undefined;
}

export function normalizeError(error: unknown, fallbackMessage = DEFAULT_HTTP_ERROR_MESSAGE) {
  if (error instanceof AppRequestError) {
    return error;
  }

  if (isAxiosError(error)) {
    const status = error.response?.status;
    const details = error.response?.data;
    const isNetworkError = !error.response;
    const message =
      isNetworkError
        ? DEFAULT_NETWORK_ERROR_MESSAGE
        : resolveHttpErrorMessage(status, details, fallbackMessage);

    return new AppRequestError(message, {
      status,
      code: extractCode(details),
      details,
      isNetworkError,
      originalError: error,
    });
  }

  if (error instanceof Error) {
    return new AppRequestError(error.message || fallbackMessage, {
      originalError: error,
    });
  }

  return new AppRequestError(fallbackMessage, {
    originalError: error,
  });
}

export function getErrorMessage(error: unknown, fallbackMessage = DEFAULT_HTTP_ERROR_MESSAGE) {
  return normalizeError(error, fallbackMessage).message;
}

export function isForbiddenError(error: unknown) {
  return normalizeError(error).status === 403;
}
