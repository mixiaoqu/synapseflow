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
    eyebrow: "资源详情",
    description: "",
    badge: "",
    loading: false,
    error: null,
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

const slots = useSlots();
const hasMeta = computed(() => Boolean(slots.meta));
const hasHeaderExtra = computed(() => Boolean(slots["header-extra"]) || Boolean(props.badge));
</script>

<template>
  <section class="flex flex-col gap-5">
    <header
      class="flex flex-col gap-4 rounded-[20px] border border-gray-200 bg-white px-[22px] py-[22px] shadow-sm sm:flex-row sm:items-start sm:justify-between"
    >
      <div class="min-w-0">
        <p class="mb-3 text-xs font-bold uppercase tracking-[0.24em] text-teal-800">
          {{ eyebrow }}
        </p>
        <h1 class="text-[clamp(24px,3vw,32px)] font-semibold leading-tight text-slate-900">
          {{ title }}
        </h1>
        <p
          v-if="description"
          class="mt-3 max-w-[640px] text-sm leading-[1.65] text-slate-600"
        >
          {{ description }}
        </p>

        <div
          v-if="hasMeta"
          class="mt-[18px] flex flex-wrap gap-3"
        >
          <slot name="meta" />
        </div>
      </div>

      <div
        v-if="hasHeaderExtra"
        class="flex flex-wrap items-center gap-3 sm:justify-end"
      >
        <slot name="header-extra" />
        <el-tag
          v-if="badge"
          type="info"
          effect="plain"
          round
        >
          {{ badge }}
        </el-tag>
      </div>
    </header>

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
