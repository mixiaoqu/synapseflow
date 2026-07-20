<script setup lang="ts">
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppForbidden from "@/shared/components/feedback/AppForbidden.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";

withDefaults(
  defineProps<{
    eyebrow?: string;
    title: string;
    description?: string;
    badge?: string;
    loading?: boolean;
    error?: unknown;
    forbidden?: boolean;
    empty?: boolean;
    loadingTitle?: string;
    loadingDescription?: string;
    emptyTitle?: string;
    emptyDescription?: string;
    errorTitle?: string;
    errorDescription?: string;
    forbiddenTitle?: string;
    forbiddenDescription?: string;
  }>(),
  {
    eyebrow: "资源详情",
    description: "",
    badge: "",
    loading: false,
    forbidden: false,
    empty: false,
    loadingTitle: "加载详情中",
    loadingDescription: "正在准备详情内容，请稍候。",
    emptyTitle: "暂无详情内容",
    emptyDescription: "当前资源还没有可展示的详情信息。",
    errorTitle: "详情加载失败",
    errorDescription: "暂时无法获取详情内容，请稍后重试。",
    forbiddenTitle: "无权查看详情",
    forbiddenDescription: "当前账号没有访问该详情页的权限。",
  },
);

defineEmits<{
  retry: [];
}>();
</script>

<template>
  <section class="flex flex-col gap-5">
    <div class="flex flex-col gap-5">
      <AppLoading
        v-if="loading"
        :title="loadingTitle"
        :description="loadingDescription"
      />

      <AppError
        v-else-if="error"
        :title="errorTitle"
        :description="errorDescription"
        :error="error"
        @retry="$emit('retry')"
      />

      <AppForbidden
        v-else-if="forbidden"
        :title="forbiddenTitle"
        :description="forbiddenDescription"
      />

      <AppEmpty
        v-else-if="empty"
        :title="emptyTitle"
        :description="emptyDescription"
      >
        <slot name="empty-actions" />
      </AppEmpty>

      <slot v-else />
    </div>
  </section>
</template>
