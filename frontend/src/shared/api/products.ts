import { request } from "@/shared/api/http";
import type { ProductListResponse, ProductSummary, ProductUpsertPayload } from "@/shared/types/product";

export function listProducts(params: { team_id?: number; page: number; page_size: number }) {
  return request<ProductListResponse>({
    url: "/products",
    method: "GET",
    params,
  });
}

export function createProduct(payload: ProductUpsertPayload) {
  return request<ProductSummary>({
    url: "/products",
    method: "POST",
    data: payload,
  });
}
