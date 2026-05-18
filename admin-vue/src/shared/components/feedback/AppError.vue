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
  }>(),
  {
    title: "加载失败",
    description: "页面内容暂时无法获取，请稍后重试。",
    error: null,
    retryText: "重新加载",
    showRetry: true,
  },
);

defineEmits<{
  retry: [];
}>();

const resolvedMessage = computed(() => getErrorMessage(props.error, props.description));
</script>

<template>
  <section class="app-error">
    <el-result
      icon="error"
      :title="title"
      :sub-title="resolvedMessage"
    >
      <template
        v-if="showRetry"
        #extra
      >
        <el-button
          type="primary"
          @click="$emit('retry')"
        >
          {{ retryText }}
        </el-button>
      </template>
    </el-result>
  </section>
</template>

<style scoped>
.app-error {
  border: 1px solid rgba(239, 68, 68, 0.18);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.9);
}
</style>
