<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string;
    description?: string;
  }>(),
  {
    title: "无权访问",
    description: "当前账号没有访问此页面的权限。",
  },
);
</script>

<template>
  <section class="app-forbidden">
    <el-result
      icon="warning"
      :title="title"
      :sub-title="description"
    />
  </section>
</template>

<style scoped>
.app-forbidden {
  border: 1px solid rgba(245, 158, 11, 0.22);
  border-radius: 24px;
  background: rgba(255, 251, 235, 0.72);
}
</style>
