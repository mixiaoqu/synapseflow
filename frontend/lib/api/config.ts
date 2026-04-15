function normalizeApiBaseUrl(value: string | undefined): string {
  if (value !== undefined) {
    return value.replace(/\/$/, "");
  }

  return process.env.NODE_ENV === "development" ? "http://localhost:8000" : "";
}

export const API_BASE = normalizeApiBaseUrl(
  typeof process !== "undefined" ? process.env?.NEXT_PUBLIC_API_URL : undefined,
);

export const API_V1 = `${API_BASE}/api/v1`;
