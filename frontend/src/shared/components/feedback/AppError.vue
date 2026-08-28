<script setup lang="ts">
import { computed } from "vue";

import { getErrorMessage } from "@/shared/utils/error";

const props = withDefaults(
  defineProps<{
    title?: string;
    description?: string;
    error?: unknown;
    retryText?: string;
    showRetry?: boolean;
    compact?: boolean;
  }>(),
  {
    title: "加载失败",
    description: "页面内容暂时无法获取，请稍后重试。",
    retryText: "重新加载",
    showRetry: true,
    compact: false,
  },
);

const emit = defineEmits<{
  retry: [];
}>();

const resolvedMessage = computed(() => getErrorMessage(props.error, props.description));
</script>

<template>
  <section class="app-state app-state--error" :class="{ 'app-state--compact': compact }">
    <el-result icon="error" :title="title" :sub-title="resolvedMessage">
      <template #extra>
        <slot name="actions">
          <el-button v-if="showRetry" type="primary" @click="emit('retry')">
            {{ retryText }}
          </el-button>
        </slot>
      </template>
    </el-result>
  </section>
</template>

<style scoped>
.app-state {
  border-radius: var(--admin-radius-lg, 20px);
  background: var(--admin-surface, #fff);
}

.app-state--error {
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.app-state--compact {
  border: 0;
  background: transparent;
}

.app-state :deep(.el-result) {
  padding: 36px 24px;
}

.app-state--compact :deep(.el-result) {
  padding: 24px 12px;
}
</style>
