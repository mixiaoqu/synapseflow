import { request } from "@/shared/api/http";
import type { AdminUser } from "@/shared/types/user";

/**
 * 获取用户列表（管理后台用）
 * @returns 用户数组
 */
export function listUsers() {
  return request<AdminUser[]>({
    url: "/users",
    method: "GET",
  });
}
