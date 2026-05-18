import { defineStore } from "pinia";

import { canAccessAdmin } from "@/shared/auth/roles";
import {
  clearAuthSession,
  getAccessToken,
  getStoredUser,
  setAuthSession,
} from "@/shared/auth/session";
import { getCurrentUser, login } from "@/shared/api/auth";
import type { CurrentUser, LoginPayload } from "@/shared/types/auth";

interface AuthState {
  user: CurrentUser | null;
  checked: boolean;
  bootstrapping: boolean;
}

export const useAuthStore = defineStore("auth", {
  state: (): AuthState => ({
    user: getStoredUser(),
    checked: false,
    bootstrapping: false,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.user && getAccessToken()),
    canAccessAdmin: (state) => canAccessAdmin(state.user),
  },
  actions: {
    async bootstrap() {
      if (this.checked || this.bootstrapping) {
        return;
      }

      const token = getAccessToken();
      if (!token) {
        this.user = null;
        this.checked = true;
        return;
      }

      this.bootstrapping = true;

      try {
        // 刷新页面后优先向后端确认当前 token 是否仍然有效，再回写本地用户信息。
        const user = await getCurrentUser();
        this.user = user;
        setAuthSession(token, user);
      } catch {
        clearAuthSession();
        this.user = null;
      } finally {
        this.checked = true;
        this.bootstrapping = false;
      }
    },
    async signIn(payload: LoginPayload) {
      const response = await login(payload);
      // 登录成功后一次性落盘 token 和用户信息，后续路由守卫直接从 store 与 session 判断状态。
      setAuthSession(response.access_token, response.user);
      this.user = response.user;
      this.checked = true;
    },
    signOut() {
      clearAuthSession();
      this.user = null;
      this.checked = true;
    },
  },
});
