<script setup lang="ts">
import { computed, useSlots } from "vue";

import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppForbidden from "@/shared/components/feedback/AppForbidden.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";

const props = withDefaults(
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
    eyebrow: "资源列表",
    description: "",
    badge: "",
    loading: false,
    error: null,
    forbidden: false,
    empty: false,
    loadingTitle: "加载列表中",
    loadingDescription: "正在准备列表内容，请稍候。",
    emptyTitle: "暂无列表数据",
    emptyDescription: "当前条件下没有可展示的列表项。",
    errorTitle: "列表加载失败",
    errorDescription: "暂时无法获取列表内容，请稍后重试。",
    forbiddenTitle: "无权查看列表",
    forbiddenDescription: "当前账号没有访问该列表的权限。",
  },
);

defineEmits<{
  retry: [];
}>();

const slots = useSlots();
const hasFilters = computed(() => Boolean(slots.filters));
</script>

<template>
  <section class="flex flex-col gap-5">
    <slot
      v-if="hasFilters"
      name="filters"
    />

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
