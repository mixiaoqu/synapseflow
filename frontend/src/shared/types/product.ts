export interface ProductSummary {
  id: number;
  team_id: number;
  team_name: string | null;
  code: string;
  name: string;
  description: string | null;
  is_active: boolean;
  project_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProductListResponse {
  items: ProductSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProductUpsertPayload {
  team_id: number;
  code: string;
  name: string;
  description?: string | null;
  is_active: boolean;
}
