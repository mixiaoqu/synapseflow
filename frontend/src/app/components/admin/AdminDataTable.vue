<script setup lang="ts" generic="Row">
import { ref, useAttrs, useSlots } from "vue";

defineOptions({
  inheritAttrs: false,
});

const attrs = useAttrs();
const slots = useSlots();
const tableRef = ref();

withDefaults(
  defineProps<{
    data: Row[];
    loading?: boolean;
    rowKey?: string;
    tableClass?: string;
    height?: string;
    loadingText?: string;
  }>(),
  {
    loading: false,
    rowKey: "id",
    tableClass: "",
    height: "var(--admin-table-height)",
    loadingText: "正在更新列表",
  },
);

defineEmits<{
  selectionChange: [selection: Row[]];
}>();

defineExpose({
  tableRef,
  clearSelection: () => tableRef.value?.clearSelection(),
  toggleRowSelection: (...args: unknown[]) => tableRef.value?.toggleRowSelection(...args),
  getSelectionRows: () => tableRef.value?.getSelectionRows(),
});
</script>

<template>
  <el-table
    ref="tableRef"
    v-bind="attrs"
    v-loading="loading"
    :data="data"
    :row-key="rowKey"
    :class="tableClass"
    :height="height"
    :element-loading-text="loadingText"
    @selection-change="$emit('selectionChange', $event)"
  >
    <slot />
    <template
      v-if="slots.empty"
      #empty
    >
      <slot name="empty" />
    </template>
  </el-table>
</template>
