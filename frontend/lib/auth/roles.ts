import type { AuthUser } from "./session";

export const ADMIN_ROLES = new Set(["kb_editor", "kb_reviewer", "kb_admin"]);
export const ROLE_OPTIONS = [
  { value: "end_user", label: "普通用户" },
  { value: "kb_editor", label: "知识编辑" },
  { value: "kb_reviewer", label: "审核人员" },
  { value: "kb_admin", label: "系统管理员" },
] as const;

export function isAdminRole(role?: string | null): boolean {
  return ADMIN_ROLES.has((role || "").trim().toLowerCase());
}

export function isKbAdmin(role?: string | null): boolean {
  return (role || "").trim().toLowerCase() === "kb_admin";
}

export function canAccessAdmin(user?: AuthUser | null): boolean {
  return Boolean(user && isAdminRole(user.role));
}
