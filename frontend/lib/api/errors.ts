type ApiErrorBody = {
  detail?: string | unknown[];
  message?: string;
};

type ApiValidationDetail = {
  loc?: unknown;
  msg?: string;
};

function formatValidationDetail(detail: unknown): string | null {
  if (!detail || typeof detail !== "object") return null;

  const item = detail as ApiValidationDetail;
  const message = typeof item.msg === "string" ? item.msg : null;
  const location = Array.isArray(item.loc)
    ? item.loc
        .filter((part) => part !== "body")
        .map((part) => String(part))
        .join(".")
    : "";

  if (!message) return location || null;
  if (!location) return message;
  return `${location}: ${message}`;
}

export async function parseApiError(res: Response): Promise<string> {
  try {
    const j = (await res.json()) as ApiErrorBody;
    if (typeof j.detail === "string") return j.detail;
    if (typeof j.message === "string") return j.message;
    if (Array.isArray(j.detail)) {
      const messages = j.detail
        .map((item) => formatValidationDetail(item) ?? JSON.stringify(item))
        .filter(Boolean);

      if (messages.length > 0) {
        return messages.join("; ");
      }
    }
  } catch {
    /* ignore */
  }

  return res.statusText || `HTTP ${res.status}`;
}
