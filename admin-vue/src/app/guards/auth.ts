import type { NavigationGuardWithThis, RouteLocationNormalized } from "vue-router";
import { ElMessage } from "element-plus";

import { useAuthStore } from "@/stores/auth";

function resolveRedirectTarget(to: RouteLocationNormalized) {
  return {
    path: "/login",
    query: {
      redirect: to.fullPath,
    },
  };
}

function handleAdminAccessDenied() {
  const authStore = useAuthStore();
  authStore.signOut();
  ElMessage.error("当前账号无后台权限");
}

export function createAuthGuard(): NavigationGuardWithThis<undefined> {
  return async (to) => {
    const authStore = useAuthStore();

    if (!authStore.checked) {
      await authStore.bootstrap();
    }

    if (to.meta.requiresAuth && !authStore.isAuthenticated) {
      return resolveRedirectTarget(to);
    }

    if (authStore.isAuthenticated && !authStore.canAccessAdmin) {
      handleAdminAccessDenied();

      if (to.path === "/login") {
        return true;
      }

      return resolveRedirectTarget(to);
    }

    if (to.meta.guestOnly && authStore.isAuthenticated) {
      return "/";
    }

    return true;
  };
}
