import { API_V1 } from "./config";
import { parseApiError } from "./errors";

export interface CollectionWithCount {
  id: number;
  name: string;
  document_count: number;
  created_at: string;
  updated_at: string;
}

export async function listCollections(): Promise<CollectionWithCount[]> {
  const res = await fetch(`${API_V1}/collections`);
  if (!res.ok) throw new Error(await parseApiError(res));
  return res.json();
}

export async function createCollection(name: string): Promise<void> {
  const res = await fetch(`${API_V1}/collections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
}
