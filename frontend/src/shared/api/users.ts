import { request } from "@/shared/api/http";
import type { AdminUser, CreateUserPayload, UpdateUserPayload, UserListResponse } from "@/shared/types/user";

/** 用户列表查询参数 */
interface ListUsersParams {
  page?: number;
  page_size?: number;
  keyword?: string;
}

/**
 * 获取用户列表（分页）
 * @param params - 分页参数（page、page_size、keyword）
 * @returns 分页用户列表响应
 */
export function listUsers(params?: ListUsersParams) {
  return request<UserListResponse>({
    url: "/users",
    method: "GET",
    params,
  });
}

/**
 * 创建新用户
 * @param payload - 用户创建数据
 * @returns 创建后的用户数据
 */
export function createUser(payload: CreateUserPayload) {
  return request<AdminUser>({
    url: "/users",
    method: "POST",
    data: payload,
  });
}

/**
 * 更新用户信息
 * @param userId - 用户 ID
 * @param payload - 更新数据
 * @returns 更新后的用户数据
 */
export function updateUser(userId: number, payload: UpdateUserPayload) {
  return request<AdminUser>({
    url: `/users/${userId}`,
    method: "PUT",
    data: payload,
  });
}
