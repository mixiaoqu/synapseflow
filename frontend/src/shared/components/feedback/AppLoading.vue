<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string;
    description?: string;
    rows?: number;
    blocks?: number;
  }>(),
  {
    title: "加载中",
    description: "正在准备页面内容，请稍候。",
    rows: 4,
    blocks: 2,
  },
);
</script>

<template>
  <section class="app-loading">
    <div class="app-loading__header">
      <h3>{{ title }}</h3>
      <p>{{ description }}</p>
    </div>

    <el-skeleton
      class="app-loading__skeleton"
      :rows="rows"
      animated
    />

    <div
      v-if="blocks > 0"
      class="app-loading__blocks"
    >
      <div
        v-for="index in blocks"
        :key="index"
        class="app-loading__block"
      >
        <el-skeleton animated>
          <template #template>
            <el-skeleton-item
              variant="rect"
              class="app-loading__block-item"
            />
          </template>
        </el-skeleton>
      </div>
    </div>
  </section>
</template>

<style scoped>
.app-loading {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 28px;
  border: 1px solid var(--panel-border);
  border-radius: 24px;
  background: var(--panel-bg);
  box-shadow: var(--panel-shadow);
}

.app-loading__header h3 {
  margin: 0;
  font-size: 18px;
}

.app-loading__header p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.app-loading__skeleton {
  --el-skeleton-color: rgba(148, 163, 184, 0.18);
  --el-skeleton-to-color: rgba(226, 232, 240, 0.56);
}

.app-loading__blocks {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}

.app-loading__block {
  overflow: hidden;
  border-radius: 20px;
}

.app-loading__block-item {
  width: 100%;
  height: 108px;
}
</style>
