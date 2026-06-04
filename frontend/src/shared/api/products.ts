import { request } from "@/shared/api/http";
import type { ProductSummary, ProductUpsertPayload } from "@/shared/types/product";

export function listProducts(teamId?: number) {
  return request<ProductSummary[]>({
    url: "/products",
    method: "GET",
    params: teamId ? { team_id: teamId } : undefined,
  });
}

export function createProduct(payload: ProductUpsertPayload) {
  return request<ProductSummary>({
    url: "/products",
    method: "POST",
    data: payload,
  });
}
