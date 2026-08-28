import { defineStore } from "pinia";

interface AdminBreadcrumbState {
  dynamicTitles: Record<string, string>;
}

export const useAdminBreadcrumbStore = defineStore("admin-breadcrumb", {
  state: (): AdminBreadcrumbState => ({
    dynamicTitles: {},
  }),
  actions: {
    setDynamicTitle(routeName: string, title: string | null | undefined) {
      const normalizedTitle = title?.trim();
      if (!normalizedTitle) {
        delete this.dynamicTitles[routeName];
        return;
      }

      this.dynamicTitles[routeName] = normalizedTitle;
    },
    clearDynamicTitles() {
      this.dynamicTitles = {};
    },
  },
});
