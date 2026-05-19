export type KnowledgeBaseStatus = "available" | "indexing" | "error" | "empty";
export type DocumentIndexStatus = "queued" | "processing" | "indexed" | "failed";

export interface KnowledgeBaseRecentDocument {
  id: number;
  title: string;
  document_type: string | null;
  size: number;
  indexed: boolean;
  index_status: DocumentIndexStatus;
  index_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeBaseSummary {
  id: number;
  name: string;
  team_id: number;
  description: string | null;
  created_at: string;
  updated_at: string;
  document_count: number;
  indexed_document_count: number;
  queued_document_count: number;
  processing_document_count: number;
  failed_document_count: number;
  unindexed_document_count: number;
  draft_document_count: number;
  submittable_document_count: number;
  pending_review_document_count: number;
  published_document_count: number;
  archived_document_count: number;
  last_document_updated_at: string | null;
  last_uploaded_at: string | null;
  status: KnowledgeBaseStatus;
  recent_documents: KnowledgeBaseRecentDocument[];
}
