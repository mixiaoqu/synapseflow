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

export interface ProjectCopyPayload {
  code: string;
  name: string;
  is_active: boolean;
}

export type ProjectBulkAction = "enable" | "disable" | "delete";

export interface ProjectBulkActionResponse {
  action: ProjectBulkAction;
  affected_ids: number[];
  affected_count: number;
}

export interface ProjectAppSummary {
  id: number;
  project_id: number;
  code: string;
  name: string;
  description: string | null;
  terminal_type: ProjectAppTerminalType;
  knowledge_base_id: number | null;
  knowledge_base_name: string | null;
  category_id: number | null;
  category_name: string | null;
  default_assistant_id: number | null;
  default_assistant_name: string | null;
  widget_version: string;
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
  terminal_type: ProjectAppTerminalType;
  knowledge_base_id?: number | null;
  category_id?: number | null;
  default_assistant_id?: number | null;
  widget_version: string;
  is_active: boolean;
}

export type ProjectAppTerminalType = "web" | "h5" | "mini_program" | "admin" | "api" | "other";

export const PROJECT_APP_TERMINAL_TYPE_LABELS: Record<ProjectAppTerminalType, string> = {
  web: "Web",
  h5: "H5",
  mini_program: "小程序",
  admin: "管理后台",
  api: "API",
  other: "其他",
};

export type ProjectAppBulkAction = "enable" | "disable" | "delete";

export interface ProjectAppBulkActionResponse {
  action: ProjectAppBulkAction;
  affected_ids: number[];
  affected_count: number;
}

export interface ProjectAppEmbedPreviewResponse {
  embed_url: string;
  expires_in_seconds: number;
}

export interface ProjectAppEmbedPreviewPayload {
  store_id?: string | null;
}
