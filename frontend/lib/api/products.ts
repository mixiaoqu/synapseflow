import { apiClient } from "./client";

export interface ProductResponse {
  id: number;
  team_id: number;
  team_name?: string | null;
  code: string;
  name: string;
  description?: string | null;
  is_active: boolean;
  project_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProductPayload {
  name: string;
  code: string;
  team_id: number;
  description?: string | null;
  is_active: boolean;
}

export const productsApi = {
  list: (filters?: { team_id?: number | null }) => {
    const params = new URLSearchParams();
    if (filters?.team_id != null) params.set("team_id", String(filters.team_id));
    return apiClient.get<ProductResponse[]>(
      `/api/v1/products${params.size > 0 ? `?${params.toString()}` : ""}`,
    );
  },

  get: (productId: number) =>
    apiClient.get<ProductResponse>(`/api/v1/products/${productId}`),

  create: (payload: ProductPayload) =>
    apiClient.post<ProductResponse>("/api/v1/products", payload),

  update: (productId: number, payload: ProductPayload) =>
    apiClient.put<ProductResponse>(`/api/v1/products/${productId}`, payload),

  delete: (productId: number) =>
    apiClient.delete<{ message: string }>(`/api/v1/products/${productId}`),
};
