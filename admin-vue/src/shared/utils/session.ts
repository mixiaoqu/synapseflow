import type { CurrentUser } from "@/shared/types/auth";

const ACCESS_TOKEN_KEY = "synapseflow.admin.access_token";
const CURRENT_USER_KEY = "synapseflow.admin.current_user";

function isBrowser() {
  return typeof window !== "undefined";
}

export function getAccessToken(): string | null {
  if (!isBrowser()) {
    return null;
  }

  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getStoredUser(): CurrentUser | null {
  if (!isBrowser()) {
    return null;
  }

  const raw = window.localStorage.getItem(CURRENT_USER_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as CurrentUser;
  } catch {
    return null;
  }
}

export function setAuthSession(token: string, user: CurrentUser) {
  if (!isBrowser()) {
    return;
  }

  window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
  window.localStorage.setItem(CURRENT_USER_KEY, JSON.stringify(user));
}

export function clearAuthSession() {
  if (!isBrowser()) {
    return;
  }

  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(CURRENT_USER_KEY);
}
