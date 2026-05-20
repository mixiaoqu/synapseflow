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

export interface ProjectAppKnowledgeBaseBinding {
  knowledge_base_id: number;
}

export interface ProjectAppKnowledgeBaseBindingResponse
  extends ProjectAppKnowledgeBaseBinding {
  knowledge_base_name: string | null;
}

export interface ProjectAppSummary {
  id: number;
  project_id: number;
  code: string;
  name: string;
  description: string | null;
  default_assistant_id: number | null;
  default_assistant_name: string | null;
  bindings: ProjectAppKnowledgeBaseBindingResponse[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectAppUpsertPayload {
  code: string;
  name: string;
  description?: string | null;
  default_assistant_id?: number | null;
  bindings: ProjectAppKnowledgeBaseBinding[];
  is_active: boolean;
}

export interface ProjectAppEmbedPreviewResponse {
  embed_url: string;
  expires_in_seconds: number;
}
