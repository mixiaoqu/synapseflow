export interface ProjectSummary {
  id: number;
  team_id: number;
  team_name: string | null;
  product_id: number;
  product_code: string | null;
  product_name: string | null;
  code: string;
  name: string;
  description: string | null;
  is_active: boolean;
  app_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectListResponse {
  items: ProjectSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProjectUpsertPayload {
  team_id: number;
  product_id: number;
  code: string;
  name: string;
  description?: string | null;
  is_active: boolean;
}

export interface ProjectAppSummary {
  id: number;
  project_id: number;
  code: string;
  name: string;
  description: string | null;
  knowledge_base_id: number | null;
  knowledge_base_name: string | null;
  category_id: number | null;
  category_name: string | null;
  default_assistant_id: number | null;
  default_assistant_name: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectAppListResponse {
  items: ProjectAppSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProjectAppUpsertPayload {
  code: string;
  name: string;
  description?: string | null;
  knowledge_base_id: number;
  category_id?: number | null;
  default_assistant_id?: number | null;
  is_active: boolean;
}

export interface ProjectAppCopyPayload {
  code: string;
  name: string;
  is_active: boolean;
}

export interface ProjectAppEmbedPreviewResponse {
  embed_url: string;
  expires_in_seconds: number;
}
