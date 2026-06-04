export type DocumentIndexStatus = "queued" | "processing" | "indexed" | "failed";
export type DocumentLifecycleStatus = "draft" | "pending_review" | "published" | "archived";

export interface DocumentSummary {
  id: number;
  title: string;
  document_type: string | null;
  size: number;
  version: number;
  is_current: boolean;
  is_latest: boolean;
  is_live: boolean;
  indexed: boolean;
  index_status: DocumentIndexStatus;
  index_error: string | null;
  indexed_at: string | null;
  graph_index_status: DocumentIndexStatus;
  graph_index_error: string | null;
  graph_indexed_at: string | null;
  knowledge_base_id: number | null;
  knowledge_base_name: string | null;
  category_id: number | null;
  category_name: string | null;
  source_path: string | null;
  status: DocumentLifecycleStatus;
  published_at: string | null;
  published_by: number | null;
  reviewed_at: string | null;
  reviewed_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentDetail extends DocumentSummary {
  content: string;
}

export interface DocumentChunkSummary {
  id: number;
  document_id: number;
  chunk_kind: string;
  parent_chunk_id: number | null;
  chunk_index: number;
  prev_chunk_id: number | null;
  next_chunk_id: number | null;
  section_path: string | null;
  block_types: string[];
  start_offset: number;
  end_offset: number;
  content: string;
  search_text: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  items: DocumentSummary[];
  total: number;
  page: number;
  page_size: number;
  status_counts: Record<string, number>;
}

export interface DocumentChunksResponse {
  items: DocumentChunkSummary[];
  total: number;
}

export interface DocumentQueueResponse {
  message: string;
  queued: number;
}

export interface BatchDocumentActionFailure {
  document_id: number;
  detail: string;
}

export interface BatchDocumentActionResponse {
  action: string;
  requested_count: number;
  succeeded_count: number;
  failed_count: number;
  succeeded_ids: number[];
  failures: BatchDocumentActionFailure[];
}
