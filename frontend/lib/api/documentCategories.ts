import { apiClient } from "./client";

export interface DocumentCategory {
  id: number;
  knowledge_base_id: number;
  name: string;
  parent_id: number | null;
  document_count: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentCategoryTreeNode {
  id: number;
  knowledge_base_id: number;
  name: string;
  parent_id: number | null;
  document_count: number;
  children: DocumentCategoryTreeNode[];
  created_at: string;
  updated_at: string;
}

export async function listDocumentCategories(
  knowledgeBaseId: number,
): Promise<DocumentCategory[]> {
  const sp = new URLSearchParams();
  sp.set("knowledge_base_id", String(knowledgeBaseId));
  return apiClient.get(`/api/v1/document-categories?${sp.toString()}`);
}

export async function listDocumentCategoriesTree(
  knowledgeBaseId: number,
): Promise<DocumentCategoryTreeNode[]> {
  const sp = new URLSearchParams();
  sp.set("knowledge_base_id", String(knowledgeBaseId));
  sp.set("format", "tree");
  return apiClient.get(`/api/v1/document-categories?${sp.toString()}`);
}

export async function createDocumentCategory(body: {
  knowledge_base_id: number;
  name: string;
  parent_id?: number | null;
}): Promise<DocumentCategory> {
  return apiClient.post("/api/v1/document-categories", body);
}

export async function updateDocumentCategory(
  categoryId: number,
  body: { name: string },
): Promise<DocumentCategory> {
  return apiClient.put(`/api/v1/document-categories/${categoryId}`, body);
}

export async function deleteDocumentCategory(categoryId: number): Promise<void> {
  await apiClient.delete(`/api/v1/document-categories/${categoryId}`);
}
