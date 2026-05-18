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
    const payload = input as ErrorPayload;

    return (
      extractMessage(payload.detail) ??
      extractMessage(payload.message) ??
      extractMessage(payload.error) ??
      null
    );
  }

  return null;
}

function extractCode(input: unknown) {
  if (!input || typeof input !== "object") {
    return undefined;
  }

  const code = (input as ErrorPayload).code;
  return typeof code === "string" && code.trim() ? code : undefined;
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
      extractMessage(details) ??
      (isNetworkError ? DEFAULT_NETWORK_ERROR_MESSAGE : null) ??
      error.message ??
      fallbackMessage;

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
