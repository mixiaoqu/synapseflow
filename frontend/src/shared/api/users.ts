import { request } from "@/shared/api/http";
import type {
  AdminUser,
  CreateUserPayload,
  UpdateUserPayload,
  UserBulkAction,
  UserListResponse,
} from "@/shared/types/user";

/** 用户列表查询参数 */
interface ListUsersParams {
  page: number;
  page_size: number;
  keyword?: string;
  role?: string;
  is_active?: boolean;
}

/**
 * 获取用户列表（分页）
 * @param params - 分页参数（page、page_size、keyword）
 * @returns 分页用户列表响应
 */
export function listUsers(params: ListUsersParams) {
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

/** 获取用户详情 */
export function getUser(userId: number) {
  return request<AdminUser>({
    url: `/users/${userId}`,
    method: "GET",
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

/** 批量操作用户 */
export function bulkActionUsers(userIds: number[], action: UserBulkAction) {
  return request<{ message: string; affected: number }>({
    url: "/users/bulk-action",
    method: "POST",
    data: {
      user_ids: userIds,
      action,
    },
  });
}

/** 软删除用户 */
export function deleteUser(userId: number) {
  return request<{ message: string }>({
    url: `/users/${userId}`,
    method: "DELETE",
  });
}
