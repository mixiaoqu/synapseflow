export interface DocumentCategorySummary {
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
