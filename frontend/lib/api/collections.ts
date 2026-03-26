import { API_V1 } from "./config";

export interface CollectionWithCount {
  id: number;
  name: string;
  document_count: number;
  created_at: string;
  updated_at: string;
}

async function parseError(res: Response): Promise<string> {
  try {
    const j = (await res.json()) as { detail?: string | unknown[] };
    if (typeof j.detail === "string") return j.detail;
    if (Array.isArray(j.detail))
      return j.detail.map((x) => JSON.stringify(x)).join("; ");
  } catch {
    /* ignore */
  }
  return res.statusText;
}

export async function listCollections(): Promise<CollectionWithCount[]> {
  const res = await fetch(`${API_V1}/collections`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function createCollection(name: string): Promise<void> {
  const res = await fetch(`${API_V1}/collections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(await parseError(res));
}
