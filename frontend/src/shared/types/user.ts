/** 管理后台用户信息 */
export interface AdminUser {
  id: number;
  username: string;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** 创建用户请求体 */
export interface CreateUserPayload {
  username: string;
  email: string;
  password: string;
  full_name?: string | null;
  role: string;
  is_active?: boolean;
}

/** 更新用户请求体 */
export interface UpdateUserPayload {
  username?: string;
  email?: string;
  password?: string;
  full_name?: string | null;
  role?: string;
  is_active?: boolean;
}

/** 角色选项 */
export const ROLE_OPTIONS = [
  { value: "end_user", label: "普通用户" },
  { value: "kb_editor", label: "知识编辑" },
  { value: "kb_reviewer", label: "审核人员" },
  { value: "kb_admin", label: "系统管理员" },
] as const;

/** 角色标签映射 */
export const ROLE_LABELS: Record<string, string> = Object.fromEntries(
  ROLE_OPTIONS.map((o) => [o.value, o.label]),
);

/** 角色对应 Element Plus Tag type */
export const ROLE_TAG_TYPES: Record<string, string> = {
  kb_admin: "danger",
  kb_reviewer: "warning",
  kb_editor: "",
  end_user: "info",
};

/** 分页用户列表响应 */
export interface UserListResponse {
  items: AdminUser[];
  total: number;
  page: number;
  page_size: number;
}
