import type { NavigationGuardWithThis, RouteLocationNormalized } from "vue-router";
import { ElMessage } from "element-plus";

import { useAuthStore } from "@/stores/auth";

// 登录跳转时保留原始目标地址，登录成功后可以回到用户最初访问的后台页面。
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
    const bypassAdminCheck = (to.meta as { bypassAdminCheck?: boolean }).bypassAdminCheck === true;

    // 首次进入路由前先恢复本地会话，避免刷新后误判成未登录。
    if (!authStore.checked) {
      await authStore.bootstrap();
    }

    if (to.meta.requiresAuth && !authStore.isAuthenticated) {
      return resolveRedirectTarget(to);
    }

    if (!bypassAdminCheck && authStore.isAuthenticated && !authStore.canAccessAdmin) {
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
