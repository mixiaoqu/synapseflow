<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string;
    description?: string;
    rows?: number;
    blocks?: number;
    compact?: boolean;
  }>(),
  {
    title: "加载中",
    description: "正在准备页面内容，请稍候。",
    rows: 4,
    blocks: 2,
    compact: false,
  },
);
</script>

<template>
  <section class="app-state app-state--loading" :class="{ 'app-state--compact': compact }">
    <div class="app-state__copy">
      <h3>{{ title }}</h3>
      <p>{{ description }}</p>
    </div>
    <el-skeleton class="app-state__skeleton" :rows="rows" animated />
    <div v-if="blocks > 0" class="app-state__blocks">
      <el-skeleton
        v-for="index in blocks"
        :key="index"
        class="app-state__block"
        animated
      >
        <template #template>
          <el-skeleton-item variant="rect" class="app-state__block-item" />
        </template>
      </el-skeleton>
    </div>
  </section>
</template>

<style scoped>
.app-state {
  border: 1px solid var(--admin-border, #e2e8f0);
  border-radius: var(--admin-radius-lg, 20px);
  background: var(--admin-surface, #fff);
  box-shadow: var(--admin-shadow-panel, 0 8px 24px rgba(15, 23, 42, 0.05));
}

.app-state--loading {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 28px;
}

.app-state--compact {
  border: 0;
  box-shadow: none;
  background: transparent;
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

.app-state__skeleton {
  --el-skeleton-color: rgba(148, 163, 184, 0.18);
  --el-skeleton-to-color: rgba(226, 232, 240, 0.56);
}

.app-state__blocks {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}

.app-state__block {
  overflow: hidden;
  border-radius: var(--admin-radius-md, 14px);
}

.app-state__block-item {
  width: 100%;
  height: 108px;
}
</style>
