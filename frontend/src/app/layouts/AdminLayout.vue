<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import AdminHeader from "@/app/components/layout/AdminHeader.vue";
import AdminSidebar from "@/app/components/layout/AdminSidebar.vue";
import { useAdminBreadcrumbStore } from "@/stores/admin-breadcrumb";

interface AdminBreadcrumb {
  label: string;
  to?: string;
}

const route = useRoute();
const router = useRouter();
const adminBreadcrumbStore = useAdminBreadcrumbStore();

const isSidebarCollapsed = ref(false);
const isMobileSidebarOpen = ref(false);

const pageTitle = computed(() => {
  if (typeof route.name === "string") {
    return adminBreadcrumbStore.dynamicTitles[route.name] || String(route.meta.title || "控制台");
  }

  return String(route.meta.title || "控制台");
});

function resolveBreadcrumbRoute(routeName: string) {
  const routeRecord = router.getRoutes().find((item) => item.name === routeName);
  const paramNames = Array.from(routeRecord?.path.matchAll(/:([A-Za-z0-9_]+)/g) ?? []).map((match) => match[1]);
  const params = Object.fromEntries(
    paramNames
      .filter((paramName) => route.params[paramName] !== undefined)
      .map((paramName) => [paramName, route.params[paramName]]),
  );

  return router.resolve({
    name: routeName,
    params,
  });
}

function getRouteTitle(routeName: string) {
  const matchedRoute = resolveBreadcrumbRoute(routeName);
  return String(
    adminBreadcrumbStore.dynamicTitles[routeName] ||
      matchedRoute.meta.breadcrumb ||
      matchedRoute.meta.title ||
      routeName,
  );
}

function buildRouteBreadcrumbs(routeName: string): AdminBreadcrumb[] {
  const matchedRoute = resolveBreadcrumbRoute(routeName);
  const parentName = typeof matchedRoute.meta.parent === "string" ? matchedRoute.meta.parent : null;
  const parentItems: AdminBreadcrumb[] = parentName ? buildRouteBreadcrumbs(parentName) : [];

  return [
    ...parentItems,
    {
      label: getRouteTitle(routeName),
      to: route.name === routeName ? undefined : matchedRoute.fullPath,
    },
  ];
}

const breadcrumbs = computed<AdminBreadcrumb[]>(() => {
  if (typeof route.name !== "string") {
    return [{ label: "管理后台", to: "/dashboard" }, { label: pageTitle.value }];
  }

  return [{ label: "管理后台", to: "/dashboard" }, ...buildRouteBreadcrumbs(route.name)];
});

function closeMobileSidebar() {
  isMobileSidebarOpen.value = false;
}
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-[var(--admin-bg)]">
    <AdminSidebar
      class="hidden lg:flex"
      :collapsed="isSidebarCollapsed"
      @toggle-collapse="isSidebarCollapsed = !isSidebarCollapsed"
    />

    <el-drawer
      v-model="isMobileSidebarOpen"
      direction="ltr"
      size="280px"
      :with-header="false"
      modal-class="admin-mobile-sidebar-modal"
      body-class="!p-0"
    >
      <AdminSidebar mobile :collapsed="false" @navigate="closeMobileSidebar" />
    </el-drawer>

    <div class="flex min-h-0 min-w-0 flex-1 flex-col">
      <AdminHeader
        :title="pageTitle"
        :breadcrumbs="breadcrumbs"
        @open-mobile-sidebar="isMobileSidebarOpen = true"
      />
      <main class="min-h-0 flex-1 overflow-y-auto p-6">
        <router-view />
      </main>
    </div>
  </div>
</template>
