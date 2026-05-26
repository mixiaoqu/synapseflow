import { request } from "@/shared/api/http";
import type {
  DocumentCategorySummary,
  DocumentCategoryTreeNode,
} from "@/shared/types/document-category";

export function listDocumentCategories(knowledgeBaseId: number) {
  return request<DocumentCategorySummary[]>({
    url: "/document-categories",
    method: "GET",
    params: {
      knowledge_base_id: knowledgeBaseId,
    },
  });
}

export function listDocumentCategoriesTree(knowledgeBaseId: number) {
  return request<DocumentCategoryTreeNode[]>({
    url: "/document-categories",
    method: "GET",
    params: {
      knowledge_base_id: knowledgeBaseId,
      format: "tree",
    },
  });
}

export function createDocumentCategory(payload: {
  knowledge_base_id: number;
  name: string;
  parent_id?: number | null;
}) {
  return request<DocumentCategorySummary>({
    url: "/document-categories",
    method: "POST",
    data: payload,
  });
}

export function updateDocumentCategory(categoryId: number, payload: { name: string }) {
  return request<DocumentCategorySummary>({
    url: `/document-categories/${categoryId}`,
    method: "PUT",
    data: payload,
  });
}

export function deleteDocumentCategory(categoryId: number) {
  return request<{ message: string }>({
    url: `/document-categories/${categoryId}`,
    method: "DELETE",
  });
}
