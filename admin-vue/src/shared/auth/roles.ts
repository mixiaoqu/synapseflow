import type { CurrentUser } from "@/shared/types/auth";

export const ADMIN_ROLES = new Set(["kb_editor", "kb_reviewer", "kb_admin"]);

export function isAdminRole(role?: string | null): boolean {
  return ADMIN_ROLES.has((role || "").trim().toLowerCase());
}

export function canAccessAdmin(user?: CurrentUser | null): boolean {
  return Boolean(user && isAdminRole(user.role));
}
