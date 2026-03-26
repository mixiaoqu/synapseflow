import { API_V1 } from "./config";

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

export type DocumentListItem = {
  id: number;
  title: string;
  document_type: string | null;
  size: number;
  version: number;
  indexed: boolean;
  collection_id: number | null;
  collection_name: string | null;
  created_at: string;
  updated_at: string;
};

export type DocumentDetail = {
  id: number;
  title: string;
  content: string;
  document_type: string | null;
  size: number;
  version: number;
  collection_id: number | null;
  created_at: string;
  updated_at: string;
};

export type DocumentVersionItem = {
  id: number;
  title: string;
  version: number;
  is_latest: boolean;
  created_at: string;
};

export async function listDocuments(params: {
  page?: number;
  page_size?: number;
  keyword?: string | null;
  collection_id?: number | null;
}): Promise<{
  items: DocumentListItem[];
  total: number;
  page: number;
  page_size: number;
}> {
  const sp = new URLSearchParams();
  if (params.page != null) sp.set("page", String(params.page));
  if (params.page_size != null) sp.set("page_size", String(params.page_size));
  if (params.keyword) sp.set("keyword", params.keyword);
  if (params.collection_id !== undefined && params.collection_id !== null) {
    sp.set("collection_id", String(params.collection_id));
  }
  const q = sp.toString();
  const res = await fetch(`${API_V1}/documents${q ? `?${q}` : ""}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function getDocument(docId: number): Promise<DocumentDetail> {
  const res = await fetch(`${API_V1}/documents/detail/${docId}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function getDocumentVersions(
  docId: number,
): Promise<DocumentVersionItem[]> {
  const res = await fetch(`${API_V1}/documents/${docId}/versions`);
  if (!res.ok) throw new Error(await parseError(res));
  const data = (await res.json()) as { items: DocumentVersionItem[] };
  return data.items;
}

export async function uploadDocument(
  file: File,
  collectionId?: number | null,
): Promise<DocumentDetail> {
  const form = new FormData();
  form.append("file", file);
  if (collectionId != null && collectionId > 0) {
    form.append("collection_id", String(collectionId));
  }
  const res = await fetch(`${API_V1}/documents`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function uploadDocumentsBatch(
  files: File[],
  collectionId?: number | null,
): Promise<DocumentDetail[]> {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  if (collectionId != null && collectionId > 0) {
    form.append("collection_id", String(collectionId));
  }
  const res = await fetch(`${API_V1}/documents/batch`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function createDocumentFromContent(body: {
  title: string;
  content: string;
  document_type?: string;
  collection_id?: number | null;
}): Promise<DocumentDetail> {
  const res = await fetch(`${API_V1}/documents/from-content`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function replaceDocumentContent(
  docId: number,
  content: string,
): Promise<DocumentDetail> {
  const res = await fetch(`${API_V1}/documents/${docId}/content`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function createDocumentVersion(
  docId: number,
  content: string,
): Promise<DocumentDetail> {
  const res = await fetch(`${API_V1}/documents/${docId}/versions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function indexDocument(
  docId: number,
): Promise<{ message: string; chunks: number }> {
  const res = await fetch(`${API_V1}/documents/${docId}/index`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function reindexAll(): Promise<{ message: string; indexed: number }> {
  const res = await fetch(`${API_V1}/documents/reindex-all`, { method: "POST" });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function deleteDocument(docId: number): Promise<void> {
  const res = await fetch(`${API_V1}/documents/${docId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await parseError(res));
}

export async function deleteDocumentsBatch(
  ids: number[],
): Promise<{ message: string; deleted: number }> {
  const sp = new URLSearchParams();
  for (const id of ids) sp.append("ids", String(id));
  const res = await fetch(`${API_V1}/documents/batch/delete?${sp.toString()}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}
