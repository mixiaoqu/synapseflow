<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    title?: string;
    description?: string;
    imageSize?: number;
  }>(),
  {
    title: "暂无数据",
    description: "当前条件下还没有可展示的内容。",
    imageSize: 120,
  },
);
</script>

<template>
  <section class="app-empty">
    <el-empty
      :image-size="props.imageSize"
      :description="props.description"
    >
      <template #description>
        <div class="app-empty__description">
          <h3>{{ props.title }}</h3>
          <p>{{ props.description }}</p>
        </div>
      </template>

      <slot />
    </el-empty>
  </section>
</template>

<style scoped>
.app-empty {
  padding: 28px;
  border: 1px dashed rgba(148, 163, 184, 0.42);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.72);
}

.app-empty__description h3 {
  margin: 0;
  font-size: 18px;
}

.app-empty__description p {
  margin: 10px 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
}
</style>
