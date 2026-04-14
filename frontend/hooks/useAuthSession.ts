"use client";

import { useCallback, useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";

import { authApi } from "@/lib/api/endpoints/auth";
import { canAccessAdmin } from "@/lib/auth/roles";
import {
  AUTH_CHANGED_EVENT,
  clearAuthSession,
  getAccessToken,
  getStoredUser,
  setAuthSession,
  type AuthUser,
} from "@/lib/auth/session";

export function useAuthSession(redirectTo: string, options?: { requireAdmin?: boolean }) {
  const router = useRouter();
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const hasValidatedRef = useRef(false);

  const redirect = useCallback(() => {
    router.replace(redirectTo);
  }, [redirectTo, router]);

  const syncSession = useCallback(async (forceRefresh = false) => {
    const token = getAccessToken();
    if (!token) {
      setCurrentUser(null);
      setAuthChecked(true);
      redirect();
      return;
    }

    const storedUser = getStoredUser();
    if (storedUser) {
      setCurrentUser(storedUser);
    }

    // Skip network validation if already validated this session (optimistic)
    // Only validate once per full page load, not on every SPA navigation
    if (!forceRefresh && hasValidatedRef.current) {
      setAuthChecked(true);
      return;
    }

    try {
      const user = await authApi.me();
      hasValidatedRef.current = true;
      setAuthSession(token, user, false);
      if (options?.requireAdmin && !canAccessAdmin(user)) {
        setCurrentUser(user);
        setAuthChecked(true);
        router.replace("/ask");
        return;
      }
      setCurrentUser(user);
    } catch {
      clearAuthSession();
      setCurrentUser(null);
      hasValidatedRef.current = false;
      redirect();
    } finally {
      setAuthChecked(true);
    }
  }, [options?.requireAdmin, redirect, router]);

  useEffect(() => {
    void syncSession();
  }, [syncSession]);

  useEffect(() => {
    const handleAuthChanged = () => {
      hasValidatedRef.current = false;
      void syncSession(true);
    };

    window.addEventListener(AUTH_CHANGED_EVENT, handleAuthChanged);
    return () => {
      window.removeEventListener(AUTH_CHANGED_EVENT, handleAuthChanged);
    };
  }, [syncSession]);

  return { currentUser, authChecked };
}
