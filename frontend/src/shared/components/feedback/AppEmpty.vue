<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string;
    description?: string;
    imageSize?: number;
    compact?: boolean;
  }>(),
  {
    title: "暂无数据",
    description: "当前条件下没有可展示的内容。",
    imageSize: 96,
    compact: false,
  },
);
</script>

<template>
  <section class="app-state app-state--empty" :class="{ 'app-state--compact': compact }">
    <el-empty :image-size="imageSize">
      <template #description>
        <div class="app-state__copy">
          <h3>{{ title }}</h3>
          <p>{{ description }}</p>
        </div>
      </template>
      <slot />
    </el-empty>
  </section>
</template>

<style scoped>
.app-state {
  border: 1px dashed var(--admin-border, rgba(148, 163, 184, 0.42));
  border-radius: var(--admin-radius-lg, 20px);
  background: var(--admin-surface, rgba(255, 255, 255, 0.72));
}

.app-state--compact {
  border: 0;
  background: transparent;
}

.app-state :deep(.el-empty) {
  padding: 28px 20px;
}

.app-state--compact :deep(.el-empty) {
  padding: 20px;
}

.app-state__copy h3 {
  margin: 0;
  color: var(--admin-text, #1f2937);
  font-size: 16px;
}

.app-state__copy p {
  margin: 8px 0 0;
  color: var(--admin-text-muted, #64748b);
  line-height: 1.6;
}
</style>
