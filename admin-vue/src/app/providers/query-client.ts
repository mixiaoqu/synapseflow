import { QueryClient, VueQueryPlugin } from "@tanstack/vue-query";

// 后台以管理台表单和列表为主，这里关闭窗口聚焦自动刷新，避免编辑过程被无意打断。
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

export const vueQueryPlugin = VueQueryPlugin;
