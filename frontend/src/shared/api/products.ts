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

export function updateProduct(productId: number, payload: ProductUpsertPayload) {
  return request<ProductSummary>({
    url: `/products/${productId}`,
    method: "PUT",
    data: payload,
  });
}

export function deleteProduct(productId: number) {
  return request<{ message: string }>({
    url: `/products/${productId}`,
    method: "DELETE",
  });
}
