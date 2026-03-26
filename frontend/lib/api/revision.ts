import { API_V1 } from "./config";

async function parseError(res: Response): Promise<string> {
  try {
    const j = (await res.json()) as { detail?: string };
    if (typeof j.detail === "string") return j.detail;
  } catch {
    /* ignore */
  }
  return res.statusText;
}

export async function suggestRevision(body: {
  document: string;
  suggestions: string;
  doc_id?: number | null;
}): Promise<{ revised_document: string }> {
  const res = await fetch(`${API_V1}/revision/suggest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      document: body.document,
      suggestions: body.suggestions,
      doc_id: body.doc_id ?? undefined,
    }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}
