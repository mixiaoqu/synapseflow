<script setup lang="ts">
withDefaults(
  defineProps<{
    currentPage: number;
    pageSize: number;
    total: number;
    pageSizes?: number[];
    layout?: string;
    background?: boolean;
    disabled?: boolean;
  }>(),
  {
    pageSizes: () => [10, 20, 50],
    layout: "total, sizes, prev, pager, next",
    background: true,
    disabled: false,
  },
);

defineEmits<{
  pageChange: [page: number];
  pageSizeChange: [pageSize: number];
}>();
</script>

<template>
  <div
    v-if="total > 0"
    class="admin-pagination"
  >
    <el-pagination
      :background="background"
      :current-page="currentPage"
      :page-size="pageSize"
      :page-sizes="pageSizes"
      :total="total"
      :layout="layout"
      :disabled="disabled"
      @current-change="$emit('pageChange', $event)"
      @size-change="$emit('pageSizeChange', $event)"
    />
  </div>
</template>

<style scoped>
.admin-pagination {
  --el-color-primary: var(--admin-primary);
  --el-pagination-hover-color: var(--admin-primary);
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--admin-border-soft);
  background: var(--admin-surface);
  padding: 12px;
}
</style>
