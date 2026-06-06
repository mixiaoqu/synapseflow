import type { CurrentUser } from "@/shared/types/auth";

export const BACKOFFICE_ROLES = new Set(["system_admin", "system_operator"]);

export function isAdminRole(role?: string | null): boolean {
  return BACKOFFICE_ROLES.has((role || "").trim().toLowerCase());
}

export function canAccessAdmin(user?: CurrentUser | null): boolean {
  return Boolean(user && isAdminRole(user.role));
}
