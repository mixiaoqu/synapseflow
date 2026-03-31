export async function parseApiError(res: Response): Promise<string> {
  try {
    const j = (await res.json()) as { detail?: string | unknown[]; message?: string };
    if (typeof j.detail === "string") return j.detail;
    if (typeof j.message === "string") return j.message;
    if (Array.isArray(j.detail)) {
      return j.detail.map((x) => JSON.stringify(x)).join("; ");
    }
  } catch {
    /* ignore */
  }

  return res.statusText || `HTTP ${res.status}`;
}
